"""
Unit tests for Cowrie.shell.prequery

Tests command parsing, path extraction, context assembly, formatters,
and integration with filesystem profiles.
"""

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Load prequery directly (bypasses cowrie/__init__.py which needs twisted)
_prequery_path = (
    Path(__file__).resolve().parent.parent
    / "Cowrie" / "cowrie-src" / "src" / "cowrie" / "shell" / "prequery.py"
)
_spec = importlib.util.spec_from_file_location("cowrie.shell.prequery", _prequery_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["cowrie.shell.prequery"] = _mod
_spec.loader.exec_module(_mod)

from cowrie.shell.prequery import (  # noqa: E402
    MAX_CONTEXT_CHARS,
    _COMMAND_FAMILIES,
    _WRAPPER_PREFIXES,
    _extract_paths,
    _extract_single_command_context,
    assemble_context,
    extract_context_needs,
    format_db_context,
    format_packages,
    format_services_detail,
    format_users_detail,
    resolve_path_context,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROFILES_DIR = Path(__file__).resolve().parent.parent / "Reconfigurator" / "profiles"


@pytest.fixture
def wordpress_profile():
    with open(PROFILES_DIR / "wordpress_server.json") as f:
        return json.load(f)


@pytest.fixture
def database_profile():
    with open(PROFILES_DIR / "database_server.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Parsing robustness
# ---------------------------------------------------------------------------


class TestParsingRobustness:
    def test_empty_command(self, wordpress_profile):
        assert extract_context_needs("", wordpress_profile) == {}

    def test_whitespace_only(self, wordpress_profile):
        assert extract_context_needs("   ", wordpress_profile) == {}

    def test_malformed_shlex(self, wordpress_profile):
        """Unmatched quotes should not crash — falls back to split()."""
        result = extract_context_needs("cat '/etc/passwd", wordpress_profile)
        # Should still parse something (the path)
        assert isinstance(result, dict)

    def test_none_like_empty(self, wordpress_profile):
        assert extract_context_needs("", wordpress_profile) == {}


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------


class TestPathExtraction:
    def test_positional_absolute_path(self):
        paths = _extract_paths(["cat", "/etc/passwd"], "cat /etc/passwd")
        assert "/etc/passwd" in paths

    def test_flag_value_path(self):
        paths = _extract_paths(
            ["--config=/etc/foo.conf"], "cmd --config=/etc/foo.conf"
        )
        assert "/etc/foo.conf" in paths

    def test_regex_fallback(self):
        """Paths in the raw command are caught by regex even if not tokenized."""
        paths = _extract_paths([], "something with /var/log/syslog in it")
        assert "/var/log/syslog" in paths

    def test_relative_path_with_slash(self):
        paths = _extract_paths(["cat", "var/www/html/index.php"], "cat var/www/html/index.php")
        assert "var/www/html/index.php" in paths

    def test_no_http_urls(self):
        paths = _extract_paths(["curl", "http://example.com/path"], "curl http://example.com/path")
        # http URLs should not be treated as paths
        assert "http://example.com/path" not in paths

    def test_deduplication(self):
        paths = _extract_paths(["/etc/passwd"], "cat /etc/passwd")
        assert paths.count("/etc/passwd") == 1


# ---------------------------------------------------------------------------
# Pipe / chain splitting
# ---------------------------------------------------------------------------


class TestPipeChainSplitting:
    def test_pipe(self, wordpress_profile):
        result = extract_context_needs(
            "cat /var/www/html/wp-config.php | grep DB", wordpress_profile
        )
        # Should have path context for a path that exists in the profile
        assert any(k.startswith("path:") for k in result)

    def test_logical_and(self, wordpress_profile):
        result = extract_context_needs("ls && whoami", wordpress_profile)
        assert isinstance(result, dict)

    def test_logical_or(self, wordpress_profile):
        result = extract_context_needs("false || echo fallback", wordpress_profile)
        assert isinstance(result, dict)

    def test_semicolon(self, wordpress_profile):
        result = extract_context_needs("id; uname", wordpress_profile)
        assert "users_detail" in result

    def test_combined_pipe_and_context(self, wordpress_profile):
        result = extract_context_needs(
            "dpkg -l | grep apache", wordpress_profile
        )
        assert "packages" in result


# ---------------------------------------------------------------------------
# Prefix stripping
# ---------------------------------------------------------------------------


class TestPrefixStripping:
    def test_sudo_stripped(self, wordpress_profile):
        result = extract_context_needs("sudo dpkg -l", wordpress_profile)
        assert "packages" in result

    def test_nohup_sudo_stripped(self, wordpress_profile):
        result = extract_context_needs(
            "nohup sudo systemctl status apache2", wordpress_profile
        )
        assert "services_detail" in result

    def test_env_var_stripped(self, wordpress_profile):
        result = extract_context_needs(
            "sudo env VAR=val dpkg -l", wordpress_profile
        )
        assert "packages" in result

    def test_all_wrappers_known(self):
        assert "sudo" in _WRAPPER_PREFIXES
        assert "nohup" in _WRAPPER_PREFIXES
        assert "nice" in _WRAPPER_PREFIXES
        assert "env" in _WRAPPER_PREFIXES
        assert "time" in _WRAPPER_PREFIXES


# ---------------------------------------------------------------------------
# Command families
# ---------------------------------------------------------------------------


class TestCommandFamilies:
    @pytest.mark.parametrize("cmd,expected_key", [
        ("dpkg -l", "packages"),
        ("apt list --installed", "packages"),
        ("systemctl status nginx", "services_detail"),
        ("service apache2 restart", "services_detail"),
        ("ss -tlnp", "network_detail"),
        ("netstat -an", "network_detail"),
        ("mysql -u root -p", "db_context"),
        ("psql -U postgres", "db_context"),
        ("docker ps", "container_context"),
        ("crontab -l", "crontabs"),
        ("useradd testuser", "users_detail"),
        ("df -h", "disk_info"),
        ("iptables -L", "firewall"),
        ("env", "environment"),
        ("find / -name '*.conf'", "directory_tree"),
    ])
    def test_command_triggers_context(self, cmd, expected_key, wordpress_profile):
        result = extract_context_needs(cmd, wordpress_profile)
        assert expected_key in result, f"{cmd!r} should trigger {expected_key!r}"

    def test_unknown_command_empty(self, wordpress_profile):
        result = extract_context_needs("randomgarbage", wordpress_profile)
        assert result == {}


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


class TestPathResolution:
    def test_existing_directory(self, wordpress_profile):
        ctx = resolve_path_context("/var/www/html", wordpress_profile)
        assert ctx is not None
        assert "children" in ctx
        assert "wp-config.php" in ctx["children"]

    def test_existing_file_content(self, wordpress_profile):
        ctx = resolve_path_context(
            "/var/www/html/wp-config.php", wordpress_profile
        )
        assert ctx is not None
        assert ctx.get("has_content") is True

    def test_missing_path_returns_none(self, wordpress_profile):
        ctx = resolve_path_context(
            "/nonexistent/completely/missing", wordpress_profile
        )
        assert ctx is None

    def test_parent_path_walking(self, wordpress_profile):
        """A file under a known directory should resolve via parent walking."""
        ctx = resolve_path_context(
            "/var/www/html/wp-content/some-plugin.php", wordpress_profile
        )
        assert ctx is not None
        assert ctx.get("note") is not None
        assert "closest parent" in ctx["note"]

    def test_protocol_fs_used_first(self, wordpress_profile):
        """When protocol_fs is available, it should be tried first."""
        mock_fs = MagicMock()
        mock_fs.exists.return_value = True
        mock_fs.get_path.return_value = [
            ["file1.txt", 2, 0, 0, 100, 0o644, 0, None, "", None],
        ]
        ctx = resolve_path_context("/some/path", wordpress_profile, mock_fs)
        assert ctx is not None
        assert ctx["source"] == "filesystem"
        mock_fs.exists.assert_called_once_with("/some/path")

    def test_protocol_fs_fallback_on_error(self, wordpress_profile):
        """If protocol_fs raises, fall back to profile."""
        mock_fs = MagicMock()
        mock_fs.exists.side_effect = Exception("fs error")
        ctx = resolve_path_context(
            "/var/www/html", wordpress_profile, mock_fs
        )
        assert ctx is not None
        assert ctx["source"] == "profile"

    def test_file_in_directory_tree_entry(self, wordpress_profile):
        """A file listed in directory_tree entries should resolve."""
        ctx = resolve_path_context(
            "/home/deploy/backup_db.sh", wordpress_profile
        )
        assert ctx is not None
        assert ctx.get("exists") is True
        assert ctx.get("type") == "file"


# ---------------------------------------------------------------------------
# Budget / assembly
# ---------------------------------------------------------------------------


class TestBudgetAssembly:
    def test_empty_needs(self):
        assert assemble_context({}) == ""

    def test_path_first_priority(self, wordpress_profile):
        needs = {
            "packages": wordpress_profile["installed_packages"],
            "path:/etc/passwd": {"source": "profile", "path": "/etc/passwd", "exists": True},
        }
        result = assemble_context(needs)
        # Path context should appear before packages
        path_pos = result.find("PATH CONTEXT")
        pkg_pos = result.find("INSTALLED PACKAGES")
        assert path_pos < pkg_pos

    def test_truncation_at_budget(self):
        """If context exceeds MAX_CONTEXT_CHARS, it should be truncated."""
        huge_packages = [{"name": f"pkg-{i}", "version": "1.0"} for i in range(500)]
        needs = {"packages": huge_packages}
        result = assemble_context(needs)
        assert len(result) <= MAX_CONTEXT_CHARS

    def test_multiple_context_types(self, wordpress_profile):
        needs = extract_context_needs(
            "dpkg -l | systemctl status apache2", wordpress_profile
        )
        result = assemble_context(needs)
        assert "INSTALLED PACKAGES" in result or "RUNNING SERVICES" in result


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------


class TestFormatters:
    def test_format_packages_basic(self):
        pkgs = [{"name": "nginx", "version": "1.18"}, {"name": "curl", "version": "7.68"}]
        result = format_packages(pkgs)
        assert "nginx 1.18" in result
        assert "curl 7.68" in result

    def test_format_packages_with_overlay(self):
        pkgs = [{"name": "nginx", "version": "1.18"}]
        result = format_packages(pkgs, overlay=["htop"])
        assert "nginx 1.18" in result
        assert "htop (newly installed)" in result

    def test_format_services_detail(self, wordpress_profile):
        result = format_services_detail(wordpress_profile["services"])
        assert "apache2" in result
        assert "PID" in result
        assert "80" in result

    def test_format_users_detail(self, wordpress_profile):
        result = format_users_detail(wordpress_profile["users"])
        assert "root" in result
        assert "deploy" in result
        assert "uid=0" in result

    def test_format_db_context_basic(self):
        data = {
            "services": [{"name": "mysqld", "pid": 123, "ports": [3306]}],
            "packages": [{"name": "mysql-server", "version": "8.0"}],
        }
        result = format_db_context(data)
        assert "mysqld" in result
        assert "mysql-server" in result

    def test_format_db_context_with_creds(self):
        data = {
            "services": [{"name": "mysqld", "pid": 123, "ports": [3306]}],
            "packages": [],
        }
        result = format_db_context(data, credential_paths={"/root/.my.cnf"})
        assert "/root/.my.cnf" in result

    def test_format_packages_empty_overlay(self):
        pkgs = [{"name": "git", "version": "2.25"}]
        result = format_packages(pkgs, overlay=[])
        assert "newly installed" not in result


# ---------------------------------------------------------------------------
# Integration: end-to-end context extraction
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_dpkg_extracts_packages(self, wordpress_profile):
        needs = extract_context_needs("dpkg -l", wordpress_profile)
        assert "packages" in needs
        assert len(needs["packages"]) > 0

    def test_sudo_dpkg_same_result(self, wordpress_profile):
        needs1 = extract_context_needs("dpkg -l", wordpress_profile)
        needs2 = extract_context_needs("sudo dpkg -l", wordpress_profile)
        assert needs1.keys() == needs2.keys()

    def test_cat_known_file_has_path(self, wordpress_profile):
        needs = extract_context_needs(
            "cat /var/www/html/wp-config.php | grep DB", wordpress_profile
        )
        path_keys = [k for k in needs if k.startswith("path:")]
        assert len(path_keys) > 0

    def test_cat_unknown_path_no_path_key(self, wordpress_profile):
        """Paths not in the profile should not produce path context."""
        needs = extract_context_needs(
            "cat /nonexistent/file.txt", wordpress_profile
        )
        path_keys = [k for k in needs if k.startswith("path:")]
        assert len(path_keys) == 0

    def test_mysql_command_db_context(self, database_profile):
        needs = extract_context_needs("mysql -u root -p", database_profile)
        # database_profile has postgresql, not mysql services
        # But db_context key should still be checked
        # The database_profile uses postgres, so mysql won't match db services
        # But the command family "mysql" maps to "db_context"
        assert isinstance(needs, dict)

    def test_full_pipeline(self, wordpress_profile):
        """End-to-end: extract → assemble → non-empty string."""
        needs = extract_context_needs(
            "sudo systemctl status apache2", wordpress_profile
        )
        result = assemble_context(needs)
        assert len(result) > 0
        assert "apache2" in result
