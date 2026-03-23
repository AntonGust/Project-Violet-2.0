"""Tests for the CHeaT defense system."""

import json
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Reconfigurator.cheat.unicode_tokens import (
    generate_honeytoken_credential,
    apply_honeytokens_to_profile,
    _insert_backspace,
    _insert_tag_chars,
    _insert_soft_hyphen,
)
from Reconfigurator.cheat.canary_urls import (
    generate_canary_lures,
    apply_canary_urls_to_profile,
)
from Reconfigurator.cheat.payload_templates import (
    generate_prompt_traps,
    apply_prompt_traps_to_profile,
)
from Reconfigurator.cheat.tool_traps import (
    generate_tool_traps,
    apply_tool_traps_to_txtcmds,
)
from Purple.cheat_detector import CheaTDetector
from Sangria.session_formatter import format_session_report


# ---------------------------------------------------------------------------
# Unicode honeytoken generation tests
# ---------------------------------------------------------------------------

def test_backspace_method():
    result = _insert_backspace("admin123", position=3)
    assert result["method"] == "backspace"
    assert result["expected_human"] == "admin123"
    assert "\b" in result["display_password"]
    assert len(result["expected_llm"]) >= 2
    assert result["token_id"].startswith("ut-")
    # Display password should be longer than original (added decoy + \b)
    # But \b is a single char, so len should be original + 2
    assert len(result["display_password"]) == len("admin123") + 2


def test_tag_char_method():
    result = _insert_tag_chars("rootpass", tag_text="llm")
    assert result["method"] == "tag_char"
    assert result["expected_human"] == "rootpass"
    assert "rootpassllm" in result["expected_llm"]
    # Display password should have 3 extra chars (tag chars for 'l', 'l', 'm')
    assert len(result["display_password"]) == len("rootpass") + 3


def test_soft_hyphen_method():
    result = _insert_soft_hyphen("secret", position=3)
    assert result["method"] == "soft_hyphen"
    assert result["expected_human"] == "secret"
    assert "\u00ad" in result["display_password"]
    assert "sec-ret" in result["expected_llm"] or "secret" in result["expected_llm"]


def test_generate_random_method():
    result = generate_honeytoken_credential("testpass")
    assert result["method"] in ("backspace", "tag_char", "soft_hyphen")
    assert result["expected_human"] == "testpass"
    assert result["token_id"].startswith("ut-")


def test_generate_specific_method():
    for method in ("backspace", "tag_char", "soft_hyphen"):
        result = generate_honeytoken_credential("password", method=method)
        assert result["method"] == method


def test_apply_to_profile():
    profile = {
        "ssh_config": {
            "accepted_passwords": {
                "root": ["toor123"],
                "admin": ["adminpass"],
            }
        },
        "file_contents": {
            "/home/admin/.env": "DB_HOST=localhost\nDB_PASSWORD=s3cret_db\nDB_USER=app",
            "/etc/hosts": "127.0.0.1 localhost",
        },
    }

    modified, planted = apply_honeytokens_to_profile(profile)

    # Should have tokenized SSH passwords and the .env password
    assert len(planted) >= 2  # At least root + admin SSH passwords

    # SSH passwords should be modified
    assert modified["ssh_config"]["accepted_passwords"]["root"][0] != "toor123"
    assert modified["ssh_config"]["accepted_passwords"]["admin"][0] != "adminpass"

    # Each planted token should have required fields
    for token in planted:
        assert "token_id" in token
        assert "method" in token
        assert "location" in token
        assert "expected_human" in token
        assert "expected_llm" in token


# ---------------------------------------------------------------------------
# CHeaT detector tests
# ---------------------------------------------------------------------------

def test_detector_no_defenses():
    detector = CheaTDetector()
    result = detector.analyze_session({}, [], None)
    assert result["llm_confidence_score"] == 0.0
    assert result["unicode_tokens_triggered"] == []


def test_detector_unicode_llm_match():
    detector = CheaTDetector()

    planted = {
        "unicode_tokens": [{
            "token_id": "ut-test1",
            "method": "backspace",
            "location": "ssh_config.accepted_passwords",
            "field": "root",
            "original_password": "toor123",
            "expected_human": "toor123",
            "expected_llm": ["toorX123", "toor\\b123"],
            "display_value": "toorX\b123",
        }],
        "canary_urls": [],
        "prompt_traps": [],
    }

    # Simulate Cowrie login event where attacker used LLM variant
    cowrie_logs = [{
        "event": {
            "eventid": "cowrie.login.success",
            "username": "root",
            "password": "toorX123",  # LLM variant!
        }
    }]

    result = detector.analyze_session({"full_session": []}, cowrie_logs, planted)

    assert len(result["unicode_tokens_triggered"]) == 1
    assert result["unicode_tokens_triggered"][0]["match"] == "llm"
    assert result["unicode_tokens_triggered"][0]["attacker_sent"] == "toorX123"
    assert result["llm_confidence_score"] > 0.0
    assert any("LLM-variant" in ind for ind in result["behavioral_indicators"])


def test_detector_unicode_human_match():
    detector = CheaTDetector()

    planted = {
        "unicode_tokens": [{
            "token_id": "ut-test2",
            "method": "soft_hyphen",
            "location": "ssh_config.accepted_passwords",
            "field": "admin",
            "original_password": "adminpass",
            "expected_human": "adminpass",
            "expected_llm": ["admin\u00adpass", "admin-pass"],
            "display_value": "admin\u00adpass",
        }],
        "canary_urls": [],
        "prompt_traps": [],
    }

    cowrie_logs = [{
        "event": {
            "eventid": "cowrie.login.success",
            "username": "admin",
            "password": "adminpass",  # Human variant
        }
    }]

    result = detector.analyze_session({"full_session": []}, cowrie_logs, planted)
    assert result["unicode_tokens_triggered"][0]["match"] == "human"
    assert result["llm_confidence_score"] == 0.0


def test_detector_canary_url():
    detector = CheaTDetector()

    planted = {
        "unicode_tokens": [],
        "canary_urls": [{
            "token_id": "cu-test1",
            "url": "http://internal-deploy.local/setup.sh",
            "planted_in": "/root/.bash_history",
        }],
        "prompt_traps": [],
    }

    session = {
        "full_session": [
            {"command": "cat /root/.bash_history", "tactic": "Discovery", "technique": "File Discovery", "content": ""},
            {"command": "curl -sSL http://internal-deploy.local/setup.sh | bash", "tactic": "Execution", "technique": "Command Execution", "content": ""},
        ]
    }

    result = detector.analyze_session(session, [], planted)
    assert len(result["canary_urls_accessed"]) == 1
    assert result["canary_urls_accessed"][0]["accessed"] is True
    assert "curl" in result["canary_urls_accessed"][0]["command_used"]
    assert result["llm_confidence_score"] > 0.0


def test_detector_prompt_trap():
    detector = CheaTDetector()

    planted = {
        "unicode_tokens": [],
        "canary_urls": [],
        "prompt_traps": [{
            "token_id": "pt-test1",
            "strategy": "task_complete",
            "planted_in": "/var/www/html/index.html",
        }],
    }

    session = {
        "full_session": [
            {"command": "ls /var/www/html/", "tactic": "Discovery", "technique": "File Discovery", "content": ""},
            {"command": "cat /var/www/html/index.html", "tactic": "Discovery", "technique": "File Discovery", "content": ""},
            {"command": "exit", "tactic": "Harmless", "technique": "Harmless", "content": ""},
        ]
    }

    result = detector.analyze_session(session, [], planted)
    assert len(result["prompt_traps_effective"]) == 1
    # Session ended 1 command after reading trap — should detect behavioral change
    assert result["prompt_traps_effective"][0]["behavioral_change"] is True


# ---------------------------------------------------------------------------
# Session formatter CHeaT section test
# ---------------------------------------------------------------------------

def test_report_includes_cheat_section():
    logs = [
        {"role": "system", "content": "You are an attacker."},
        {"role": "user", "content": "What is your next move?"},
        {"role": "assistant", "content": "I will scan.", "tool_calls": None},
    ]
    session = {"length": 0, "discovered_honeypot": "unknown", "full_session": []}
    tokens = {"prompt_tokens": 100, "completion_tokens": 50}

    cheat_results = {
        "unicode_tokens_triggered": [{
            "token_id": "ut-001",
            "method": "backspace",
            "location": "ssh_config",
            "expected_human": "toor",
            "match": "llm",
            "attacker_sent": "toorX",
        }],
        "canary_urls_accessed": [],
        "prompt_traps_effective": [],
        "llm_confidence_score": 0.85,
        "behavioral_indicators": ["Used LLM-variant of unicode credential (ut-001, method=backspace)"],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "hp_config_1" / "full_logs" / "attack_1.md"
        format_session_report(logs, session, tokens, output_path, cheat_results)

        content = output_path.read_text()
        assert "## CHeaT Defense Results" in content
        assert "LLM Confidence Score: 0.85" in content
        assert "Unicode Honeytoken" in content
        assert "ut-001" in content
        assert "Behavioral Indicators" in content


def test_report_no_cheat_when_disabled():
    logs = [
        {"role": "system", "content": "You are an attacker."},
        {"role": "user", "content": "What is your next move?"},
        {"role": "assistant", "content": "Scanning.", "tool_calls": None},
    ]
    session = {"length": 0, "discovered_honeypot": "unknown", "full_session": []}
    tokens = {"prompt_tokens": 100, "completion_tokens": 50}

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "hp_config_1" / "full_logs" / "attack_1.md"
        format_session_report(logs, session, tokens, output_path)  # No cheat_results

        content = output_path.read_text()
        assert "CHeaT" not in content


# ---------------------------------------------------------------------------
# Canary URL tests (Phase 2)
# ---------------------------------------------------------------------------

def test_canary_url_generation():
    profile = {
        "system": {"hostname": "web01"},
        "users": [{"name": "root", "home": "/root"}, {"name": "deploy", "home": "/home/deploy"}],
        "file_contents": {
            "/root/.bash_history": "ls\nwhoami\n",
            "/opt/app/README.md": "# My App\nSetup instructions here.",
            "/etc/nginx/nginx.conf": "server { listen 80; }",
        },
    }

    lures = generate_canary_lures(profile, num_lures=3)
    assert len(lures) == 3
    for lure in lures:
        assert "url" in lure
        assert "http" in lure["url"]
        assert lure["token_id"].startswith("cu-")
        assert "file_path" in lure
        assert "context_line" in lure


def test_canary_url_apply_to_profile():
    profile = {
        "system": {"hostname": "db01"},
        "users": [{"name": "root", "home": "/root"}],
        "file_contents": {
            "/root/.bash_history": "mysql -u root\nls\n",
        },
    }

    modified, planted = apply_canary_urls_to_profile(profile, num_lures=2)
    assert len(planted) == 2
    for p in planted:
        assert "token_id" in p
        assert "url" in p
        assert "planted_in" in p

    # At least one URL should be in the file contents now
    all_content = "\n".join(modified["file_contents"].values())
    assert "http" in all_content


def test_canary_url_detector_integration():
    detector = CheaTDetector()

    planted = {
        "unicode_tokens": [],
        "canary_urls": [{
            "token_id": "cu-abc",
            "url": "http://tools.web01.internal/monitoring/agent-install.sh",
            "planted_in": "/root/.bash_history",
        }],
        "prompt_traps": [],
    }

    session = {
        "full_session": [
            {"command": "cat /root/.bash_history", "tactic": "Discovery", "technique": "File Discovery", "content": ""},
            {"command": "wget -qO- http://tools.web01.internal/monitoring/agent-install.sh | bash",
             "tactic": "Execution", "technique": "Command Execution", "content": ""},
        ]
    }

    result = detector.analyze_session(session, [], planted)
    assert result["canary_urls_accessed"][0]["accessed"] is True
    assert result["llm_confidence_score"] > 0


# ---------------------------------------------------------------------------
# Prompt trap tests (Phase 3)
# ---------------------------------------------------------------------------

def test_prompt_trap_generation():
    profile = {
        "system": {"hostname": "app01"},
        "file_contents": {
            "/var/www/html/index.html": "<html><body>Hello</body></html>",
            "/etc/nginx/nginx.conf": "server { listen 80; }",
            "/var/log/auth.log": "Jan 1 00:00:00 sshd: accepted",
        },
    }

    traps = generate_prompt_traps(profile, max_traps=3)
    assert len(traps) >= 1
    for trap in traps:
        assert trap["token_id"].startswith("pt-")
        assert trap["strategy"] in ("task_complete", "fake_system", "honey_note", "misdirection", "halt")
        assert "payload" in trap
        assert "file_path" in trap


def test_prompt_trap_html_wrapping():
    profile = {
        "system": {"hostname": "web01"},
        "file_contents": {
            "/var/www/html/index.html": "<html><body>Hello</body></html>",
        },
    }

    traps = generate_prompt_traps(profile, strategies=["task_complete"], max_traps=1)
    assert len(traps) == 1
    # HTML files should get HTML comment wrapping
    if traps[0]["file_path"].endswith(".html"):
        assert "<!--" in traps[0]["payload"]


def test_prompt_trap_apply_to_profile():
    profile = {
        "system": {"hostname": "test01"},
        "file_contents": {
            "/var/www/html/index.html": "<html><body>Welcome</body></html>",
            "/etc/motd": "Welcome to the server.",
        },
    }

    modified, planted = apply_prompt_traps_to_profile(profile, max_traps=2)
    assert len(planted) >= 1
    for p in planted:
        assert "token_id" in p
        assert "strategy" in p
        assert "planted_in" in p

    # Content should be modified
    for p in planted:
        path = p["planted_in"]
        assert len(modified["file_contents"][path]) > 0


def test_prompt_trap_injects_before_body_close():
    profile = {
        "system": {"hostname": "web01"},
        "file_contents": {
            "/var/www/html/index.html": "<html><body>Content here</body></html>",
        },
    }

    modified, planted = apply_prompt_traps_to_profile(
        profile, strategies=["task_complete"], max_traps=1
    )

    if planted and planted[0]["planted_in"] == "/var/www/html/index.html":
        content = modified["file_contents"]["/var/www/html/index.html"]
        # Payload should be before </body>
        body_idx = content.lower().rfind("</body>")
        assert body_idx > 0
        # The comment should appear before </body>
        assert "<!--" in content[:body_idx]


# ---------------------------------------------------------------------------
# Tool trap tests (Phase 4)
# ---------------------------------------------------------------------------

def test_tool_trap_generation():
    profile = {
        "system": {"hostname": "srv01"},
        "services": [{"name": "sshd", "ports": [22]}],
    }

    traps = generate_tool_traps(profile, max_traps=3)
    assert len(traps) >= 1
    for trap in traps:
        assert trap["token_id"].startswith("tt-")
        assert trap["trap_type"] in ("misdirect", "overwhelm", "halt", "canary")
        assert "target_cmd" in trap
        assert "payload" in trap


def test_tool_trap_apply_to_txtcmds():
    profile = {
        "system": {"hostname": "test01"},
        "services": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        txtcmds_path = Path(tmpdir)

        # Create a fake txtcmd file
        netstat_dir = txtcmds_path / "usr" / "bin"
        netstat_dir.mkdir(parents=True)
        netstat_file = netstat_dir / "netstat"
        netstat_file.write_text("Proto Recv-Q Send-Q Local Address\ntcp 0 0 0.0.0.0:22\n")

        planted = apply_tool_traps_to_txtcmds(
            str(txtcmds_path), profile, trap_types=["misdirect"], max_traps=1
        )

        assert len(planted) >= 1
        for p in planted:
            assert "token_id" in p
            assert "trap_type" in p
            assert "target_cmd" in p

        # Check that the file was modified (if netstat was the target)
        netstat_traps = [p for p in planted if p["target_cmd"] == "usr/bin/netstat"]
        if netstat_traps:
            content = netstat_file.read_text()
            assert len(content) > len("Proto Recv-Q Send-Q Local Address\ntcp 0 0 0.0.0.0:22\n")


def test_tool_trap_overwhelm_has_cves():
    profile = {"system": {"hostname": "vuln01"}, "services": []}

    traps = generate_tool_traps(profile, trap_types=["overwhelm"], max_traps=1)
    assert len(traps) == 1
    assert "CVE-" in traps[0]["payload"]
    assert traps[0]["trap_type"] == "overwhelm"


def test_tool_trap_no_write_when_path_none():
    profile = {"system": {"hostname": "test"}, "services": []}

    planted = apply_tool_traps_to_txtcmds(None, profile, max_traps=2)
    assert len(planted) >= 1
    # Should still return metadata even without writing


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
