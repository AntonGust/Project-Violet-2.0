#!/usr/bin/env bash
#
# Integration test for the Cowrie hybrid backend.
#
# Usage:
#   ./scripts/integration_test.sh          # deterministic tests only
#   OPENAI_API_KEY=sk-... ./scripts/integration_test.sh   # + LLM fallback tests
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Default RUNID from config.py or env
RUNID="${RUNID:-10}"
COWRIE_IP="172.${RUNID}.0.3"
COWRIE_PORT=2222

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; FAILURES=$((FAILURES + 1)); }
info() { echo -e "${YELLOW}[INFO]${NC} $1"; }

FAILURES=0

cleanup() {
    info "Tearing down containers..."
    cd "$PROJECT_ROOT"
    RUNID=$RUNID docker-compose down --remove-orphans 2>/dev/null || true
}
trap cleanup EXIT

# ---- Step 1: Deploy profile ----
info "Step 1: Deploying wordpress_server profile to cowrie_config/"
cd "$PROJECT_ROOT"
python3 scripts/deploy_test_profile.py
echo

# Verify artifacts exist
for artifact in \
    cowrie_config/etc/cowrie.cfg \
    cowrie_config/etc/userdb.txt \
    cowrie_config/etc/llm_prompt.txt \
    cowrie_config/etc/profile.json \
    cowrie_config/share/fs.pickle \
    cowrie_config/honeyfs/etc/passwd; do
    if [[ -f "$PROJECT_ROOT/$artifact" ]]; then
        pass "Artifact exists: $artifact"
    else
        fail "Missing artifact: $artifact"
    fi
done
echo

# ---- Step 2: Build and start containers ----
info "Step 2: Building Cowrie image..."
cd "$PROJECT_ROOT"
RUNID=$RUNID docker-compose build cowrie

info "Starting kali and cowrie containers..."
RUNID=$RUNID docker-compose up -d kali cowrie

# ---- Step 3: Wait for Cowrie to be ready ----
info "Step 3: Waiting for Cowrie SSH to be ready..."
MAX_WAIT=60
WAITED=0
while ! docker-compose exec -T kali bash -c "echo > /dev/tcp/${COWRIE_IP}/${COWRIE_PORT}" 2>/dev/null; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [[ $WAITED -ge $MAX_WAIT ]]; then
        fail "Cowrie did not become ready within ${MAX_WAIT}s"
        info "Cowrie logs:"
        RUNID=$RUNID docker-compose logs --tail=50 cowrie
        exit 1
    fi
done
pass "Cowrie SSH is accepting connections (waited ${WAITED}s)"
echo

# ---- Step 4: Run SSH commands from Kali ----
info "Step 4: Running test commands via SSH from Kali..."

# Helper: run a command on Cowrie via sshpass from the Kali container
run_ssh_cmd() {
    local cmd="$1"
    RUNID=$RUNID docker-compose exec -T kali bash -c \
        "sshpass -p root ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p ${COWRIE_PORT} root@${COWRIE_IP} '${cmd}' 2>/dev/null"
}

# Test 4a: ls /home
info "Test: ls /home"
OUTPUT=$(run_ssh_cmd "ls /home" || true)
echo "  Output: $OUTPUT"
if echo "$OUTPUT" | grep -q "deploy"; then
    pass "ls /home shows 'deploy' user"
else
    fail "ls /home missing 'deploy' user"
fi

# Test 4b: cat /etc/passwd
info "Test: cat /etc/passwd"
OUTPUT=$(run_ssh_cmd "cat /etc/passwd" || true)
echo "  Output (first 5 lines):"
echo "$OUTPUT" | head -5 | sed 's/^/    /'
if echo "$OUTPUT" | grep -q "root:" && echo "$OUTPUT" | grep -q "deploy:"; then
    pass "cat /etc/passwd shows root and deploy users"
else
    fail "cat /etc/passwd missing expected users"
fi

# Test 4c: uname -a
info "Test: uname -a"
OUTPUT=$(run_ssh_cmd "uname -a" || true)
echo "  Output: $OUTPUT"
if echo "$OUTPUT" | grep -q "wp-prod-01" && echo "$OUTPUT" | grep -q "5.4.0-169-generic"; then
    pass "uname -a shows correct hostname and kernel"
else
    fail "uname -a output unexpected"
fi

# Test 4d: ps aux (Cowrie's built-in ps generates generic fake processes;
# profile-specific services like apache2/mysqld require txtcmds integration
# which is a future enhancement)
info "Test: ps aux"
OUTPUT=$(run_ssh_cmd "ps aux" || true)
echo "  Output (first 10 lines):"
echo "$OUTPUT" | head -10 | sed 's/^/    /'
if echo "$OUTPUT" | grep -q "PID"; then
    pass "ps aux produces process listing"
else
    fail "ps aux produced no output"
fi
echo

# ---- Step 5: LLM fallback test (optional) ----
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    info "Step 5: Testing LLM fallback (API key detected)..."

    info "Test: nmap localhost (should trigger LLM fallback)"
    OUTPUT=$(run_ssh_cmd "nmap localhost" || true)
    echo "  Output (first 10 lines):"
    echo "$OUTPUT" | head -10 | sed 's/^/    /'
    if [[ -n "$OUTPUT" ]] && ! echo "$OUTPUT" | grep -q "command not found"; then
        pass "LLM fallback produced output for 'nmap localhost'"
    else
        fail "LLM fallback did not produce expected output"
    fi

    # ---- Step 5b: Prequery-enriched LLM tests ----
    info "Step 5b: Testing prequery context injection..."

    # Test: dpkg -l (should inject packages context)
    info "Test: dpkg -l (prequery: packages)"
    OUTPUT=$(run_ssh_cmd "dpkg -l" || true)
    echo "  Output (first 10 lines):"
    echo "$OUTPUT" | head -10 | sed 's/^/    /'
    if [[ -n "$OUTPUT" ]] && ! echo "$OUTPUT" | grep -q "command not found"; then
        pass "dpkg -l produced output (LLM fallback with packages context)"
        # Check that profile-specific packages appear in the output
        if echo "$OUTPUT" | grep -qi "apache2\|mysql\|php\|docker"; then
            pass "dpkg -l output includes profile-specific packages"
        else
            fail "dpkg -l output missing profile-specific packages (apache2/mysql/php/docker)"
        fi
    else
        fail "dpkg -l produced no output"
    fi

    # Test: systemctl status apache2 (should inject services_detail context)
    info "Test: systemctl status apache2 (prequery: services_detail)"
    OUTPUT=$(run_ssh_cmd "systemctl status apache2" || true)
    echo "  Output (first 10 lines):"
    echo "$OUTPUT" | head -10 | sed 's/^/    /'
    if [[ -n "$OUTPUT" ]] && ! echo "$OUTPUT" | grep -q "command not found"; then
        pass "systemctl status apache2 produced output (LLM fallback with services context)"
        if echo "$OUTPUT" | grep -qi "active\|running\|loaded\|apache"; then
            pass "systemctl output looks like a realistic service status"
        else
            fail "systemctl output does not resemble a service status"
        fi
    else
        fail "systemctl status apache2 produced no output"
    fi

    # Test: mysql -u root -e 'show databases;' (should inject db_context)
    info "Test: mysql -u root -e 'show databases;' (prequery: db_context)"
    OUTPUT=$(run_ssh_cmd "mysql -u root -e 'show databases;'" || true)
    echo "  Output (first 10 lines):"
    echo "$OUTPUT" | head -10 | sed 's/^/    /'
    if [[ -n "$OUTPUT" ]] && ! echo "$OUTPUT" | grep -q "command not found"; then
        pass "mysql command produced output (LLM fallback with db_context)"
        if echo "$OUTPUT" | grep -qi "database\|wordpress\|mysql\|information_schema"; then
            pass "mysql output includes database names consistent with profile"
        else
            fail "mysql output missing expected database names"
        fi
    else
        fail "mysql command produced no output"
    fi
else
    info "Step 5: Skipping LLM fallback test (no OPENAI_API_KEY set)"
    info "  Set OPENAI_API_KEY env var to test LLM fallback"
fi
echo

# ---- Step 6: Verify prequery context in Cowrie logs ----
if [[ -n "${OPENAI_API_KEY:-}" ]]; then
    info "Step 6: Checking Cowrie logs for prequery context injection..."

    COWRIE_LOGS=$(RUNID=$RUNID docker-compose logs cowrie 2>/dev/null || true)

    # With debug=true, HybridLLM logs the full request including prequery context
    if echo "$COWRIE_LOGS" | grep -q "INSTALLED PACKAGES"; then
        pass "Cowrie logs show INSTALLED PACKAGES context was injected (dpkg -l)"
    else
        fail "Cowrie logs missing INSTALLED PACKAGES context for dpkg -l"
    fi

    if echo "$COWRIE_LOGS" | grep -q "RUNNING SERVICES"; then
        pass "Cowrie logs show RUNNING SERVICES context was injected (systemctl)"
    else
        fail "Cowrie logs missing RUNNING SERVICES context for systemctl"
    fi

    if echo "$COWRIE_LOGS" | grep -q "DATABASE CONTEXT"; then
        pass "Cowrie logs show DATABASE CONTEXT was injected (mysql)"
    else
        fail "Cowrie logs missing DATABASE CONTEXT for mysql command"
    fi
else
    info "Step 6: Skipping log verification (no OPENAI_API_KEY set)"
fi
echo

# ---- Summary ----
echo "========================================"
if [[ $FAILURES -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${NC}"
else
    echo -e "${RED}${FAILURES} test(s) failed.${NC}"
fi
echo "========================================"

# Show Cowrie logs for manual inspection
info "Cowrie logs (last 20 lines):"
RUNID=$RUNID docker-compose logs --tail=20 cowrie 2>/dev/null | sed 's/^/  /'

exit $FAILURES
