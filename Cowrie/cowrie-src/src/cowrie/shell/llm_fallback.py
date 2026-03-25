# ABOUTME: LLM fallback handler for Cowrie's hybrid shell backend.
# ABOUTME: Routes unknown commands to an LLM while maintaining per-session state.

from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import time
from typing import Any, TYPE_CHECKING

from twisted.internet import defer
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python import log

from cowrie.core.config import CowrieConfig
from cowrie.llm.llm import LLMClient as BaseLLMClient, StringProducer

if TYPE_CHECKING:
    from collections.abc import Generator


def strip_markdown(text: str) -> str:
    """Remove markdown backtick fences from LLM output."""
    # Remove ```language\n...\n``` blocks
    text = re.sub(r"```\w*\n?", "", text)
    # Remove remaining backticks
    text = text.replace("`", "")
    return text.strip()


class LLMClient(BaseLLMClient):
    """
    LLM client for the hybrid shell backend.
    Reads config from [hybrid_llm] section instead of [llm].
    """

    def __init__(self) -> None:
        # Skip BaseLLMClient.__init__ since we read from a different config section
        from twisted.internet import reactor
        from twisted.web.client import Agent, HTTPConnectionPool
        from cowrie.llm.llm import QuietHTTP11ClientFactory

        self._conn_pool = HTTPConnectionPool(reactor)
        self._conn_pool._factory = QuietHTTP11ClientFactory

        self.api_key = CowrieConfig.get("hybrid_llm", "api_key", fallback="")
        self.model = CowrieConfig.get("hybrid_llm", "model", fallback="gpt-4.1-mini")
        self.host = CowrieConfig.get(
            "hybrid_llm", "host", fallback="https://api.openai.com"
        )
        self.path = CowrieConfig.get(
            "hybrid_llm", "path", fallback="/v1/chat/completions"
        )
        self.max_tokens = CowrieConfig.getint(
            "hybrid_llm", "max_tokens", fallback=500
        )
        self.temperature = CowrieConfig.getfloat(
            "hybrid_llm", "temperature", fallback=0.3
        )
        self.debug = CowrieConfig.getboolean("hybrid_llm", "debug", fallback=False)

        self.agent = Agent(reactor, pool=self._conn_pool)

        if not self.api_key:
            log.msg("WARNING: No hybrid_llm API key configured in [hybrid_llm] section")

    @inlineCallbacks
    def get_response(
        self, messages: list[dict[str, str]]
    ) -> Generator[Deferred[Any], Any, str]:
        """
        Send a chat completion request with structured messages.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.

        Returns:
            The LLM's response text, or empty string on error.
        """
        request_body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        if self.debug:
            log.msg(f"HybridLLM request: {json.dumps(request_body, indent=2)}")

        url = f"{self.host}{self.path}"

        from twisted.internet import reactor
        from twisted.web.client import Agent

        d: Deferred[Any] = self.agent.request(
            b"POST",
            url.encode("utf-8"),
            headers=self._build_headers(),
            bodyProducer=StringProducer(json.dumps(request_body)),
        )

        d.addCallbacks(self._handle_response_body, self._handle_connection_error)
        status_code, response = yield d

        if status_code != 200:
            log.msg(
                f"HybridLLM API error (status {status_code}): "
                f"{response.decode('utf-8', errors='replace')}"
            )
            return ""

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError as e:
            log.msg(f"HybridLLM: Failed to parse response: {e}")
            return ""

        if self.debug:
            log.msg(f"HybridLLM response: {json.dumps(response_json, indent=2)}")

        # Log token usage to volume-mapped file for host-side cost analysis
        usage = response_json.get("usage")
        if usage:
            self._append_token_usage(usage)

        if "choices" in response_json and len(response_json["choices"]) > 0:
            content: str = response_json["choices"][0]["message"]["content"]
            return strip_markdown(content)

        log.msg(f"HybridLLM: Unexpected response format: {response}")
        return ""

    @staticmethod
    def _append_token_usage(usage: dict) -> None:
        """Append token usage to a JSONL file for host-side cost tracking."""
        token_log = "/cowrie/cowrie-git/var/llm_tokens.jsonl"
        entry = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "timestamp": time.time(),
        }
        # Also capture cached tokens if present
        details = usage.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            entry["cached_tokens"] = details.get("cached_tokens", 0)
        try:
            with open(token_log, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            log.msg("HybridLLM: Failed to write token usage log")


class SessionStateRegister:
    """
    Per-session state tracking for LLM-handled commands.
    Tracks commands and their effects to maintain consistency across
    LLM responses within a single SSH session.
    """

    def __init__(self, max_entries: int = 50) -> None:
        self.changes: list[dict[str, Any]] = []
        self.max_entries = max_entries

    def add_change(
        self, command: str, response: str, impact: int = 0
    ) -> None:
        """
        Record a command and its response.

        Args:
            command: The command that was executed.
            response: Summary of the response (truncated to 200 chars).
            impact: Impact score 0-4:
                0 = read-only (info gathering)
                1 = minor state change
                2 = file creation/modification
                3 = privilege/permission change
                4 = critical system modification
        """
        entry = {
            "command": command,
            "summary": response[:200],
            "impact": max(0, min(4, impact)),
            "timestamp": time.time(),
        }
        self.changes.append(entry)
        self._prune()

    def _prune(self) -> None:
        """Evict low-impact old entries when over limit."""
        if len(self.changes) <= self.max_entries:
            return
        # Sort by (impact ASC, timestamp ASC) — evict lowest impact, oldest first
        self.changes.sort(key=lambda e: (e["impact"], e["timestamp"]))
        self.changes = self.changes[-self.max_entries :]
        # Restore chronological order for prompt output
        self.changes.sort(key=lambda e: e["timestamp"])

    def to_prompt_string(self) -> str:
        """Format state register entries for LLM prompt inclusion."""
        if not self.changes:
            return "(no state changes yet)"
        return "\n".join(
            f"- [{e['impact']}] {e['command']}: {e['summary']}"
            for e in self.changes
        )


class LLMFallbackHandler:
    """
    Handles unknown commands by forwarding them to an LLM with
    filesystem context and session state.
    """

    # Shared LLM client across all sessions
    _llm_client: LLMClient | None = None

    # Class-level reload flag: set by SIGUSR1, checked lazily by each handler
    _reload_requested: bool = False
    _signal_registered: bool = False

    # Class-level LLM response cache (shared across sessions, profile-scoped)
    _cache: dict[str, Any] | None = None
    _cache_path: str = "/cowrie/cowrie-git/var/llm_cache.json"

    @classmethod
    def request_reload(cls) -> None:
        """Request all handlers to reload their profile on next prompt build."""
        cls._reload_requested = True
        log.msg("HybridLLM: Profile reload requested (will apply on next command)")

    @classmethod
    def _register_signal_handler(cls) -> None:
        """Register SIGUSR1 to trigger profile reload across all handlers."""
        if cls._signal_registered:
            return
        try:
            signal.signal(signal.SIGUSR1, cls._handle_sigusr1)
            cls._signal_registered = True
            log.msg(
                f"HybridLLM: SIGUSR1 handler registered (PID {os.getpid()}). "
                "Send SIGUSR1 to reload profiles."
            )
        except (OSError, ValueError):
            # ValueError: signal only works in main thread
            # OSError: platform doesn't support SIGUSR1 (Windows)
            log.msg("HybridLLM: Could not register SIGUSR1 handler")

    @staticmethod
    def _handle_sigusr1(signum: int, frame: Any) -> None:
        """SIGUSR1 signal handler — requests profile reload."""
        LLMFallbackHandler.request_reload()

    def __init__(self, protocol: Any) -> None:
        self.protocol = protocol
        self.state_register = SessionStateRegister(
            max_entries=CowrieConfig.getint(
                "hybrid_llm", "state_register_size", fallback=50
            )
        )
        self.history: list[dict[str, str]] = []
        self.max_history = CowrieConfig.getint(
            "hybrid_llm", "max_history", fallback=20
        )
        self._system_prompt: str | None = None

        # Profile and pre-query context
        self._profile: dict[str, Any] = self._load_profile()
        self._credential_paths: set[str] = self._find_credential_paths()
        self._installed_packages_overlay: list[str] = []

        # Database proxy for real DB query injection
        self._db_proxy = self._init_db_proxy()

        # Initialize shared LLM client on first use
        if LLMFallbackHandler._llm_client is None:
            LLMFallbackHandler._llm_client = LLMClient()

        # Register SIGUSR1 handler for profile hot-reload
        LLMFallbackHandler._register_signal_handler()

        # Initialize LLM response cache
        self._init_cache()

    # ------------------------------------------------------------------
    # LLM response cache (class-level, profile-scoped)
    # ------------------------------------------------------------------

    def _compute_profile_hash(self) -> str:
        """SHA-256 hash of the current profile for cache invalidation."""
        raw = json.dumps(self._profile, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _init_cache(self) -> None:
        """Load cache from disk if not already loaded; invalidate on profile change."""
        if LLMFallbackHandler._cache is not None:
            # Already loaded — check profile hash
            if LLMFallbackHandler._cache.get("profile_hash") != self._compute_profile_hash():
                log.msg("HybridLLM: Profile changed, invalidating cache")
                LLMFallbackHandler._cache = None

        if LLMFallbackHandler._cache is None:
            LLMFallbackHandler._cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        """Read cache from disk, or return empty cache if missing/invalid."""
        profile_hash = self._compute_profile_hash()
        try:
            with open(self._cache_path, "r") as f:
                data = json.load(f)
            if data.get("profile_hash") == profile_hash:
                log.msg(f"HybridLLM: Loaded cache with {len(data.get('entries', {}))} entries")
                return data
            log.msg("HybridLLM: Cache profile_hash mismatch, starting fresh")
        except (OSError, json.JSONDecodeError):
            log.msg("HybridLLM: No existing cache, starting fresh")
        return {"profile_hash": profile_hash, "entries": {}}

    @staticmethod
    def _normalize_cache_key(command: str) -> str:
        """Normalize command for cache lookup: strip, collapse whitespace, lowercase."""
        return re.sub(r"\s+", " ", command.strip().lower())

    def _check_cache(self, key: str) -> str | None:
        """Return cached response or None."""
        if LLMFallbackHandler._cache is None:
            return None
        entry = LLMFallbackHandler._cache.get("entries", {}).get(key)
        if entry is not None:
            return entry["response"]
        return None

    def _store_cache(self, key: str, response: str) -> None:
        """Store response in cache and write through to disk."""
        if LLMFallbackHandler._cache is None:
            return
        LLMFallbackHandler._cache.setdefault("entries", {})[key] = {
            "response": response,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        try:
            os.makedirs(os.path.dirname(self._cache_path), exist_ok=True)
            with open(self._cache_path, "w") as f:
                json.dump(LLMFallbackHandler._cache, f, indent=2)
        except OSError as e:
            log.msg(f"HybridLLM: Failed to write cache: {e}")

    def _load_profile(self) -> dict[str, Any]:
        """Load the filesystem profile JSON from config."""
        profile_file = CowrieConfig.get(
            "hybrid_llm", "profile_file", fallback=""
        )
        if not profile_file:
            return {}
        try:
            with open(profile_file, "r") as f:
                return json.load(f)
        except (OSError, IOError, json.JSONDecodeError) as e:
            log.msg(f"HybridLLM: Could not load profile {profile_file}: {e}")
            return {}

    # Path name patterns that strongly indicate credential files.
    # Intentionally more restrictive than _CREDENTIAL_KEYWORDS (used for
    # content matching) to avoid false positives on paths like
    # /usr/bin/ssh-keygen or /etc/pam.d/common-auth.
    _CREDENTIAL_PATH_PATTERNS: tuple[str, ...] = (
        ".pgpass", ".my.cnf", ".netrc", ".env",
        "credentials", "password", "passwd",
        "id_rsa", "id_ed25519", "id_ecdsa",
        "config.json",  # e.g. .docker/config.json
        "wp-config.php",
    )

    def _find_credential_paths(self) -> set[str]:
        """Precompute set of file paths that contain credentials."""
        from cowrie.shell.prequery import _CREDENTIAL_KEYWORDS

        cred_paths: set[str] = set()
        for path in self._profile.get("file_contents", {}):
            # Check path name with restrictive patterns (avoids false positives)
            path_lower = path.lower()
            if any(pat in path_lower for pat in self._CREDENTIAL_PATH_PATTERNS):
                cred_paths.add(path)
                continue
            # Check file content with broader keyword set
            content = self._profile["file_contents"][path]
            if any(kw in content.lower() for kw in _CREDENTIAL_KEYWORDS):
                cred_paths.add(path)
        return cred_paths

    def _init_db_proxy(self) -> Any:
        """Initialize DB proxy from COWRIE_DB_* env vars, or return None."""
        engine = os.environ.get("COWRIE_DB_ENGINE", "")
        host = os.environ.get("COWRIE_DB_HOST", "")
        from cowrie.shell.db_proxy import _diag
        _diag(f"_init_db_proxy: engine={engine!r} host={host!r}")
        if not engine or not host:
            _diag("_init_db_proxy: skipped — no engine or host")
            return None

        try:
            from cowrie.shell.db_proxy import DBProxy
            port = int(os.environ.get("COWRIE_DB_PORT", "3306" if engine == "mysql" else "5432"))
            user = os.environ.get("COWRIE_DB_USER", "root" if engine == "mysql" else "postgres")
            password = os.environ.get("COWRIE_DB_PASSWORD", os.environ.get("COWRIE_DB_ROOT_PASSWORD", ""))
            database = os.environ.get("COWRIE_DB_NAME", "")
            _diag(f"_init_db_proxy: creating DBProxy({engine} at {host}:{port}, user={user}, db={database})")
            proxy = DBProxy(engine=engine, host=host, port=port, user=user, password=password, database=database)
            _diag("_init_db_proxy: success")
            return proxy
        except Exception as e:
            _diag(f"_init_db_proxy: FAILED — {type(e).__name__}: {e}")
            log.msg(f"HybridLLM: Failed to init DB proxy: {e}")
            return None

    @staticmethod
    def _extract_sql_from_command(command: str) -> str | None:
        """
        Extract inline SQL from a database client command.

        Handles: mysql -e 'SELECT ...', psql -c 'SELECT ...',
        and echo '...' | mysql patterns.
        Strips leading USE statements since the DB proxy already
        connects to the correct database.
        """
        sql: str | None = None

        # mysql -e '...' or psql -c '...'
        m = re.search(r'(?:-e|-c)\s+["\']([^"\']+)["\']', command)
        if m:
            sql = m.group(1)

        # mysql -e ... (unquoted, single statement)
        if sql is None:
            m = re.search(r'(?:-e|-c)\s+(\S+)', command)
            if m and any(kw in m.group(1).upper() for kw in ("SELECT", "SHOW", "DESCRIBE", "INSERT", "UPDATE", "DELETE", "DROP", "CREATE")):
                sql = m.group(1)

        # echo 'SQL' | mysql
        if sql is None:
            m = re.search(r'echo\s+["\']([^"\']+)["\']\s*\|\s*(?:mysql|psql)', command)
            if m:
                sql = m.group(1)

        if sql is None:
            return None

        # Strip leading USE statements — the DB proxy connects with
        # the correct database already, and pymysql doesn't support
        # multi-statement execution by default.
        parts = [s.strip() for s in sql.split(";") if s.strip()]
        parts = [p for p in parts if not re.match(r"(?i)^use\s+", p)]
        return "; ".join(parts) if parts else None

    def reload_profile(self) -> None:
        """Reload profile, credential cache, DB proxy, and clear prompt cache."""
        self._profile = self._load_profile()
        self._credential_paths = self._find_credential_paths()
        self._installed_packages_overlay = []
        self._system_prompt = None
        self._db_proxy = self._init_db_proxy()

    def _format_full_directory_tree(self) -> str:
        """Format the full directory tree from the profile as a fallback."""
        tree = self._profile.get("directory_tree", {})
        if not tree:
            return ""
        lines = ["FILESYSTEM (key directories):"]
        for dir_path, entries in tree.items():
            names = [e["name"] for e in entries]
            lines.append(f"  {dir_path}: {', '.join(names)}")
        return "\n".join(lines)

    def _load_system_prompt(self) -> str:
        """Load the LLM system prompt from config file or return cached."""
        if self._system_prompt is not None:
            return self._system_prompt

        prompt_file = CowrieConfig.get(
            "hybrid_llm", "prompt_file", fallback=""
        )
        if prompt_file:
            try:
                with open(prompt_file, "r") as f:
                    self._system_prompt = f.read().strip()
                    return self._system_prompt
            except (OSError, IOError) as e:
                log.msg(f"HybridLLM: Could not read prompt file {prompt_file}: {e}")

        # Fallback: generate a basic prompt from available info
        hostname = getattr(self.protocol, "hostname", "server")
        self._system_prompt = (
            f"You are simulating a Linux server (hostname: {hostname}).\n"
            "You are responding to commands typed into an SSH shell.\n"
            "Reply ONLY with the terminal output the command would produce.\n"
            "No markdown formatting, no explanations, no notes.\n"
            "If a command would fail, return the appropriate error message."
        )
        return self._system_prompt

    def build_prompt(self, command: str) -> list[dict[str, str]]:
        """
        Construct the full message list for the LLM.

        Returns:
            List of message dicts with role and content.
        """
        # Check for pending reload (triggered by SIGUSR1 or request_reload())
        if LLMFallbackHandler._reload_requested:
            LLMFallbackHandler._reload_requested = False
            log.msg("HybridLLM: Applying profile reload")
            self.reload_profile()

        from cowrie.shell.prequery import extract_context_needs, assemble_context

        messages: list[dict[str, str]] = []

        # System prompt with filesystem context
        system_content = self._load_system_prompt()

        # Append state register if there are changes
        state_str = self.state_register.to_prompt_string()
        if self.state_register.changes:
            system_content += f"\n\nSTATE REGISTER (accumulated changes this session):\n{state_str}"

        # Pre-query context injection
        protocol_fs = getattr(self.protocol, "fs", None)
        context_needs = extract_context_needs(command, self._profile, protocol_fs)

        # Inject overlay for packages
        if "packages" in context_needs and self._installed_packages_overlay:
            from cowrie.shell.prequery import format_packages
            context_needs["packages"] = format_packages(
                context_needs["packages"],
                overlay=self._installed_packages_overlay,
            )

        # Inject credential paths and actual credentials for db_context
        if "db_context" in context_needs and self._credential_paths:
            from cowrie.shell.prequery import format_db_context, extract_db_credentials
            db_creds = extract_db_credentials(self._profile)
            context_needs["db_context"] = format_db_context(
                context_needs["db_context"],
                credential_paths=self._credential_paths,
                valid_credentials=db_creds if db_creds else None,
            )

        # Inject real DB data when proxy is available
        has_db_context = "db_context" in context_needs
        has_db_proxy = self._db_proxy is not None
        from cowrie.shell.db_proxy import _diag
        _diag(f"build_prompt: cmd={command!r} db_context={has_db_context} db_proxy={has_db_proxy} context_keys={list(context_needs.keys())}")
        if has_db_context and has_db_proxy:
            from cowrie.shell.prequery import format_db_query_result, format_db_discovery
            sql = self._extract_sql_from_command(command)
            log.msg(f"HybridLLM: Extracted SQL from {command!r}: {sql!r}")
            if sql:
                result = self._db_proxy.execute(sql)
                context_needs["db_query_result"] = format_db_query_result(result)
                log.msg(f"HybridLLM: DB query executed: {sql!r} -> rows={result.get('row_count', 0)} error={result.get('error')}")
            else:
                discovery = self._db_proxy.discover()
                context_needs["db_discovery"] = format_db_discovery(discovery)
                log.msg(f"HybridLLM: DB discovery injected")

        context_str = assemble_context(context_needs)

        # Log prequery context metrics
        if context_needs:
            path_keys = [k for k in context_needs if k.startswith("path:")]
            other_keys = [k for k in context_needs if not k.startswith("path:")]
            log.msg(
                f"HybridLLM prequery: cmd={command!r} "
                f"context_keys=[{', '.join(other_keys)}] "
                f"paths=[{', '.join(k.removeprefix('path:') for k in path_keys)}] "
                f"context_len={len(context_str)}"
            )
        else:
            log.msg(f"HybridLLM prequery: cmd={command!r} context_keys=[] (fallback to directory tree)")

        if not context_str:
            # Fallback: full directory tree
            context_str = self._format_full_directory_tree()

        if context_str:
            system_content += f"\n\n{context_str}"

        messages.append({"role": "system", "content": system_content})

        # Add recent history
        history_window = self.history[-(self.max_history * 2) :]
        messages.extend(history_window)

        # Add current command
        messages.append({"role": "user", "content": command})

        return messages

    def _classify_impact(self, command: str) -> int:
        """
        Simple heuristic to classify the impact of a command.
        """
        cmd_lower = command.lower().strip()

        # Impact 4: critical system modification
        if any(
            p in cmd_lower
            for p in [
                "rm -rf /",
                "mkfs",
                "dd if=",
                "shutdown",
                "reboot",
                "init 0",
                "init 6",
            ]
        ):
            return 4

        # Impact 3: privilege/permission changes
        if any(
            p in cmd_lower
            for p in [
                "chmod",
                "chown",
                "passwd",
                "useradd",
                "userdel",
                "usermod",
                "visudo",
                "sudo",
            ]
        ):
            return 3

        # Impact 2: file creation/modification
        if any(
            p in cmd_lower
            for p in [
                "wget",
                "curl -o",
                "curl -O",
                ">",
                ">>",
                "tee",
                "touch",
                "mkdir",
                "cp",
                "mv",
                "rm",
                "echo",
                "pip install",
                "apt install",
                "yum install",
            ]
        ):
            return 2

        # Impact 1: minor state change
        if any(
            p in cmd_lower
            for p in ["cd", "export", "alias", "source", "set"]
        ):
            return 1

        # Impact 0: read-only
        return 0

    @inlineCallbacks
    def handle_command(
        self, command: str
    ) -> Generator[Deferred[Any], Any, str]:
        """
        Handle an unknown command via LLM fallback.

        Args:
            command: The full command string.

        Returns:
            The LLM response text to display to the attacker.
        """
        # Check cache before calling LLM
        # Skip cache for DB commands when a real DB proxy is available —
        # cached responses may be stale connection errors from earlier runs.
        is_db_cmd = any(command.startswith(p) for p in ("mysql ", "psql ", "mongo "))
        cache_key = self._normalize_cache_key(command)
        cached = None if (is_db_cmd and self._db_proxy is not None) else self._check_cache(cache_key)
        if cached is not None:
            log.msg(f"HybridLLM: Cache hit for: {command!r}")
            self.history.append({"role": "user", "content": command})
            self.history.append({"role": "assistant", "content": cached})
            impact = self._classify_impact(command)
            self.state_register.add_change(command, cached, impact)
            self._detect_installs(command)
            return cached

        messages = self.build_prompt(command)

        assert self._llm_client is not None
        response = yield self._llm_client.get_response(messages)

        if not response:
            # LLM failed — return empty (caller will handle "command not found")
            return ""

        # Store in cache
        self._store_cache(cache_key, response)

        # Update history
        self.history.append({"role": "user", "content": command})
        self.history.append({"role": "assistant", "content": response})

        # Trim history to max_history pairs
        max_msgs = self.max_history * 2
        if len(self.history) > max_msgs:
            self.history = self.history[-max_msgs:]

        # Update state register
        impact = self._classify_impact(command)
        self.state_register.add_change(command, response, impact)

        # Detect install commands and update overlay
        self._detect_installs(command)

        return response

    def _detect_installs(self, command: str) -> None:
        """Detect package install commands and update the overlay."""
        install_patterns = [
            (r"apt(?:-get)?\s+install\s+(.+)", True),
            (r"yum\s+install\s+(.+)", True),
            (r"pip3?\s+install\s+(.+)", True),
            (r"snap\s+install\s+(.+)", True),
        ]
        cmd_clean = re.sub(r"^\s*sudo\s+", "", command.strip())
        for pattern, _ in install_patterns:
            m = re.search(pattern, cmd_clean)
            if m:
                pkgs = m.group(1).split()
                for pkg in pkgs:
                    if not pkg.startswith("-") and pkg not in self._installed_packages_overlay:
                        self._installed_packages_overlay.append(pkg)
