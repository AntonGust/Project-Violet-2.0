#!/bin/bash
# restore_lure_secrets.sh — Restore realistic honeypot lure credentials
#
# GitHub push protection blocks tokens that match real secret patterns
# (glc_, sk_live_, glpat-, glsa_, hooks.slack.com). The committed files
# use safe placeholders. Run this script AFTER checkout to restore
# realistic values for honeypot deployment.
#
# Secret mappings are stored in scripts/.lure_secrets (gitignored).
#
# Usage:  ./scripts/restore_lure_secrets.sh
# Reverse: ./scripts/restore_lure_secrets.sh --sanitize  (restore placeholders)

set -euo pipefail
cd "$(dirname "$0")/.."

SANITIZE=false
if [[ "${1:-}" == "--sanitize" ]]; then
    SANITIZE=true
fi

SECRETS_FILE="scripts/.lure_secrets"
if [[ ! -f "$SECRETS_FILE" ]]; then
    echo "ERROR: $SECRETS_FILE not found."
    echo "This file contains the secret mappings and is not committed to git."
    echo "Copy it from a teammate or restore from your secure backup."
    exit 1
fi

# ── Read secret mappings from file ────────────────────────────────
SECRETS=()
while IFS= read -r line; do
    # Skip comments and blank lines
    [[ -z "$line" || "$line" == \#* ]] && continue
    SECRETS+=("$line")
done < "$SECRETS_FILE"

# ── Files to process ────────────────────────────────────────────────
FILES=(
    Reconfigurator/profiles/backup_server.json
    Reconfigurator/profiles/docker_swarm.json
    Reconfigurator/profiles/monitoring_stack.json
    Reconfigurator/profiles/cicd_runner.json
    Reconfigurator/profiles/database_server.json
    Reconfigurator/profiles/dev_workstation.json
    cowrie_config_hop2/etc/profile.json
    cowrie_config_hop3/etc/profile.json
    cowrie_config_hop3/honeyfs/var/lib/gitlab-runner/.gitlab-ci.yml
    cowrie_config_hop3/honeyfs/var/lib/jenkins/workspace/deploy-production/Jenkinsfile
    cowrie_config_hop2/honeyfs/home/dba/.gitlab-ci.yml
    cowrie_config_hop4/etc/profile.json
    cowrie_config_hop4/etc/llm_prompt.txt
    cowrie_config_hop4/honeyfs/home/sysops/.grafana_api_token
    cowrie_config_hop4/honeyfs/home/sysops/.bash_history
    cowrie_config_hop4/honeyfs/home/sysops/alertmanager_config_backup.yml
    cowrie_config_hop4/honeyfs/root/.bash_history
)

count=0
for file in "${FILES[@]}"; do
    [[ -f "$file" ]] || continue
    for entry in "${SECRETS[@]}"; do
        placeholder="${entry%%|*}"
        real_value="${entry##*|}"

        if $SANITIZE; then
            # Replace real → placeholder (for committing)
            if grep -qF "$real_value" "$file" 2>/dev/null; then
                sed -i "s|${real_value}|${placeholder}|g" "$file"
                echo "  sanitized: $file (${placeholder:0:40}...)"
                count=$((count + 1))
            fi
        else
            # Replace placeholder → real (for deployment)
            if grep -qF "$placeholder" "$file" 2>/dev/null; then
                sed -i "s|${placeholder}|${real_value}|g" "$file"
                echo "  restored:  $file (${real_value:0:40}...)"
                count=$((count + 1))
            fi
        fi
    done
done

# Handle complex multi-line secrets via Python helper
if $SANITIZE; then
    python3 "$(dirname "$0")/gcp_lure.py" --sanitize
    echo "Sanitized $count replacements. Safe to commit/push."
else
    python3 "$(dirname "$0")/gcp_lure.py" --restore
    echo "Restored $count lure secrets. Ready for honeypot deployment."
fi
