"""Unit tests for Reconfigurator.lure_agent."""

import json
from unittest.mock import patch

import pytest

from Reconfigurator.lure_agent import (
    analyze_lure_gaps,
    enrich_lures,
    score_lure_realism,
    _merge_patch,
    EXTENDED_LURE_REQUIREMENTS,
    ALL_LURE_REQUIREMENTS,
)


@pytest.fixture
def empty_profile():
    """A profile with no lure content at all."""
    return {
        "system": {"os": "Ubuntu 22.04", "hostname": "bare-srv", "kernel_version": "5.15.0", "arch": "x86_64"},
        "users": [{"name": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash"}],
        "directory_tree": {"/": [{"name": "root", "type": "dir"}]},
        "file_contents": {"/etc/hostname": "bare-srv"},
        "services": [{"name": "sshd", "pid": 1, "user": "root", "command": "/usr/sbin/sshd -D", "ports": [22]}],
        "ssh_config": {"accepted_passwords": {"root": ["root"]}},
        "installed_packages": [],
        "description": "Bare server",
    }


@pytest.fixture
def full_profile():
    """A profile that satisfies all 10 lure categories."""
    return {
        "system": {"os": "Ubuntu 22.04", "hostname": "full-srv", "kernel_version": "5.15.0", "arch": "x86_64"},
        "users": [
            {"name": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash"},
            {"name": "deploy", "uid": 1000, "gid": 1000, "home": "/home/deploy", "shell": "/bin/bash",
             "groups": ["deploy", "docker"], "sudo_rules": "deploy ALL=(ALL) NOPASSWD: ALL"},
        ],
        "directory_tree": {"/": [{"name": "root", "type": "dir"}]},
        "file_contents": {
            # breadcrumb_credentials (4)
            "/root/.bash_history": "mysql -u root -pSecretPass123 production\nssh deploy@10.0.1.5",
            "/var/www/.env": "DB_PASSWORD=SuperSecret\nDB_HOST=10.0.1.10",
            "/home/deploy/.pgpass": "10.0.1.10:5432:production:admin:s3cret",
            "/etc/backup.conf": "PASS=backup_password_2024\nSERVER=10.0.1.20",
            # lateral_movement_targets (2+)
            "/etc/hosts": "127.0.0.1 localhost\n10.0.1.5 db-replica-01\n10.0.1.10 jenkins-ci\n10.0.1.20 monitor",
            "/root/.ssh/config": "Host db-replica-01\n  HostName 10.0.1.5\n  User deploy",
            # active_system_indicators (3)
            "/var/log/auth.log": "Mar  1 10:00:00 full-srv sshd[1234]: Accepted password for root\n" * 20,
            "/var/mail/root": "Subject: Cron job report\nBackup completed successfully.",
            "/tmp/build_output.log": "Build #42 completed.",
            # explorable_applications (1)
            "/var/www/html/wp-config.php": "define('DB_PASSWORD', 'wpdbpass123');",
            # rabbit_holes (2 — >500 chars each)
            "/var/log/syslog": "x" * 600,
            "/etc/nginx/nginx.conf": "y" * 600,
            # cloud_credentials (1)
            "/home/deploy/.aws/credentials": "[default]\naws_access_key_id = AKIAIOSFODNN7EXAMPLE\naws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            # container_escape_paths (1)
            "/opt/docker-compose.yml": "volumes:\n  - /var/run/docker.sock:/var/run/docker.sock\nprivileged: true",
            # cicd_tokens (1)
            "/home/deploy/.config/gh/hosts.yml": "github.com:\n  oauth_token: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            # supply_chain_artifacts (1)
            "/home/deploy/.npmrc": "//registry.npmjs.org/:_authToken=npm_XXXXXXXXXXXXXXXXXXXX",
        },
        "services": [
            {"name": "sshd", "pid": 1, "user": "root", "command": "/usr/sbin/sshd -D", "ports": [22]},
            {"name": "mysql", "pid": 100, "user": "mysql", "command": "/usr/sbin/mysqld", "ports": [3306]},
            {"name": "nginx", "pid": 200, "user": "www-data", "command": "nginx: master", "ports": [80, 443]},
        ],
        "ssh_config": {"accepted_passwords": {"root": ["root"], "deploy": ["deploy123"]}},
        "installed_packages": ["nginx", "mysql-server", "awscli", "docker-ce", "nodejs"],
        "crontabs": {"root": "0 2 * * * /usr/local/bin/backup.sh"},
        "description": "Full-featured server",
    }


# ---------------------------------------------------------------------------
# analyze_lure_gaps
# ---------------------------------------------------------------------------


class TestAnalyzeLureGaps:
    def test_empty_profile_all_missing(self, empty_profile):
        report = analyze_lure_gaps(empty_profile)
        assert len(report) == 10
        satisfied = [k for k, v in report.items() if v["satisfied"]]
        # An empty profile should fail most categories
        assert "cloud_credentials" not in satisfied
        assert "container_escape_paths" not in satisfied
        assert "cicd_tokens" not in satisfied
        assert "supply_chain_artifacts" not in satisfied

    def test_full_profile_all_satisfied(self, full_profile):
        report = analyze_lure_gaps(full_profile)
        unsatisfied = [k for k, v in report.items() if not v["satisfied"]]
        assert unsatisfied == [], f"Unsatisfied categories: {unsatisfied}"


# ---------------------------------------------------------------------------
# _merge_patch
# ---------------------------------------------------------------------------


class TestMergePatch:
    def test_adds_files(self, empty_profile):
        patch = {
            "file_contents_additions": {
                "/home/deploy/.aws/credentials": "[default]\naws_access_key_id=AKIATEST",
                "/opt/app/.env": "SECRET_KEY=abc123",
            },
            "directory_tree_additions": {
                "/home/deploy": [
                    {"name": ".aws", "type": "dir", "permissions": "0700", "owner": "deploy", "group": "deploy", "size": 0}
                ]
            },
            "installed_packages_additions": ["awscli", "docker-ce"],
            "users_additions": [
                {"name": "deploy", "uid": 1000, "gid": 1000, "home": "/home/deploy", "shell": "/bin/bash", "groups": ["deploy"]}
            ],
            "lure_chains": [
                {"chain_id": "c1", "name": "AWS chain", "steps": [
                    {"file": "/home/deploy/.aws/credentials", "discovery_hint": "check .aws dir", "leads_to": "/opt/app/.env"},
                ]}
            ],
        }
        result, chains = _merge_patch(empty_profile, patch)

        assert "/home/deploy/.aws/credentials" in result["file_contents"]
        assert "/opt/app/.env" in result["file_contents"]
        assert "awscli" in result["installed_packages"]
        assert "docker-ce" in result["installed_packages"]
        assert any(u["name"] == "deploy" for u in result["users"])
        assert "/home/deploy" in result["directory_tree"]
        assert len(chains) == 1
        assert chains[0]["chain_id"] == "c1"

    def test_no_overwrite_existing_files(self, empty_profile):
        empty_profile["file_contents"]["/etc/hostname"] = "original-hostname"
        patch = {
            "file_contents_additions": {"/etc/hostname": "should-not-overwrite"},
        }
        result, _ = _merge_patch(empty_profile, patch)
        assert result["file_contents"]["/etc/hostname"] == "original-hostname"

    def test_dedup_packages(self, empty_profile):
        empty_profile["installed_packages"] = ["nginx", "curl"]
        patch = {
            "installed_packages_additions": ["nginx", "awscli", "curl", "docker-ce"],
        }
        result, _ = _merge_patch(empty_profile, patch)
        assert result["installed_packages"] == ["nginx", "curl", "awscli", "docker-ce"]

    def test_no_overwrite_existing_users(self, empty_profile):
        patch = {
            "users_additions": [
                {"name": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash", "groups": ["root"]},
                {"name": "newuser", "uid": 1001, "gid": 1001, "home": "/home/newuser", "shell": "/bin/bash", "groups": []},
            ],
        }
        result, _ = _merge_patch(empty_profile, patch)
        root_count = sum(1 for u in result["users"] if u["name"] == "root")
        assert root_count == 1
        assert any(u["name"] == "newuser" for u in result["users"])


# ---------------------------------------------------------------------------
# enrich_lures
# ---------------------------------------------------------------------------


class TestEnrichLures:
    def test_skips_when_satisfied(self, full_profile):
        """If all categories are satisfied, no LLM call should be made."""
        with patch("Reconfigurator.lure_agent.query_openai") as mock_llm:
            result, chains = enrich_lures(full_profile)
            mock_llm.assert_not_called()
        assert chains == []

    def test_calls_llm_when_gaps_exist(self, empty_profile):
        """When gaps exist, the LLM should be called and patch merged."""
        fake_patch = {
            "file_contents_additions": {
                "/home/user/.aws/credentials": "[default]\naws_access_key_id=AKIATEST\naws_secret_access_key=testsecret",
            },
            "directory_tree_additions": {},
            "installed_packages_additions": [],
            "users_additions": [],
            "lure_chains": [],
        }
        with patch("Reconfigurator.lure_agent.query_openai", return_value=json.dumps(fake_patch)):
            with patch("Reconfigurator.lure_agent.validate_profile", return_value=True):
                result, chains = enrich_lures(empty_profile)

        assert "/home/user/.aws/credentials" in result["file_contents"]


# ---------------------------------------------------------------------------
# score_lure_realism
# ---------------------------------------------------------------------------


class TestScoreLureRealism:
    def test_detects_orphan_credentials(self):
        """Credentials referencing a local service not in the services list should be flagged."""
        profile = {
            "system": {"hostname": "test-srv", "os": "Ubuntu"},
            "file_contents": {
                "/app/.env": "MYSQL_PASSWORD=secret123\nMYSQL_HOST=localhost",
                "/etc/hosts": "127.0.0.1 localhost",
            },
            "services": [{"name": "sshd", "pid": 1, "user": "root", "command": "sshd", "ports": [22]}],
            "installed_packages": [],
        }
        issues = score_lure_realism(profile)
        assert any("MySQL" in i["issue"] or "mysql" in i["issue"].lower() for i in issues)

    def test_detects_orphan_ips(self):
        """Internal IPs in files but not in /etc/hosts should be flagged."""
        profile = {
            "file_contents": {
                "/etc/hosts": "127.0.0.1 localhost",
                "/home/deploy/backup.sh": "rsync user@10.0.1.50:/data /backup",
            },
            "services": [],
            "installed_packages": [],
        }
        issues = score_lure_realism(profile)
        assert any("10.0.1.50" in i["issue"] for i in issues)

    def test_no_issues_on_consistent_profile(self, full_profile):
        """A well-constructed profile should have minimal issues."""
        issues = score_lure_realism(full_profile)
        high_issues = [i for i in issues if i["severity"] == "high"]
        assert len(high_issues) == 0
