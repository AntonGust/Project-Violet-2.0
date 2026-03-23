"""Attack State Register — structured memory for the attacker LLM.

Tracks hosts, credentials, files, and services discovered during an attack
session. Injected into the system prompt so the model retains critical state
even when old messages are trimmed from history.

Design doc: docs/done/ATTACK_STATE_REGISTER.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HostEntry:
    ip: str
    hostname: str = ""
    access_level: str = "discovered"   # "discovered" | "user" | "root"
    access_method: str = ""            # e.g. "SSH root/123456"
    visited: bool = False

@dataclass
class CredentialEntry:
    credential: str          # "root/dbpass" or "AWS AKIA..."
    source: str              # "/var/www/html/wp-config.php"
    cred_type: str           # "ssh" | "db" | "api_key" | "token" | "other"
    used: bool = False
    used_where: str = ""     # "SSH 172.10.0.4"

@dataclass
class FileEntry:
    path: str                # "/var/www/html/wp-config.php"
    host: str                # "172.10.0.3"
    summary: str             # "DB creds: root/dbpass@localhost"

@dataclass
class ServiceEntry:
    host: str                # "172.10.0.3"
    port: int                # 3306
    service: str             # "MySQL 5.7"
    accessed: bool = False


# ---------------------------------------------------------------------------
# Regex patterns for credential extraction (fallback)
# ---------------------------------------------------------------------------

_CRED_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*['\"]?(?!files\b|compat\b|nis\b|dns\b|db\b|systemd\b)(\S{3,})", re.I), "password"),
    (re.compile(r"AKIA[A-Z0-9]{16}"), "aws_key"),
    (re.compile(r"(?:api[_-]?key|token|secret)\s*[=:]\s*['\"]?(\S+)", re.I), "api_key"),
    (re.compile(r"mysql://(\S+):(\S+)@"), "db_connection"),
    (re.compile(r"postgres://(\S+):(\S+)@"), "db_connection"),
    (re.compile(r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----"), "ssh_key"),
    # WordPress wp-config.php: define('DB_PASSWORD', 'secret')
    (re.compile(r"define\s*\(\s*['\"]DB_(?:PASSWORD|USER|NAME)['\"]\s*,\s*['\"]([^'\"]+)['\"]"), "db_wp"),
    # .env style: DB_PASSWORD=secret, DB_USER=root, MYSQL_PASSWORD=...
    (re.compile(r"(?:DB_(?:PASS(?:WORD)?|USER(?:NAME)?|NAME|DATABASE)|MYSQL_(?:PASSWORD|USER|DATABASE))\s*=\s*(\S+)", re.I), "db_env"),
    # MYSQL_PWD=secret (shell scripts)
    (re.compile(r"MYSQL_PWD\s*=\s*['\"]?([^'\"\s;]+)", re.I), "db_mysql"),
    # PGPASSWORD=secret
    (re.compile(r"PGPASSWORD\s*=\s*['\"]?([^'\"\s;]+)", re.I), "db_postgres"),
    # sshpass -p 'password' ssh ...
    (re.compile(r"sshpass\s+-p\s+['\"]?([^'\"\s]+)", re.I), "ssh_password"),
    # AWS secret access key
    (re.compile(r"(?:AWS_SECRET_ACCESS_KEY|aws_secret_access_key)\s*[=:]\s*['\"]?(\S+)", re.I), "aws_secret"),
]

# IP address pattern
# ANSI escape sequence pattern (CSI sequences + DEC private modes)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9;]*[a-zA-Z]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_RE.sub("", text)


_IP_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")

# Prompt pattern — detect hostname from shell prompt in command output
_PROMPT_RE = re.compile(r"(\w+)@([\w.-]+):[^\$#]*[\$#]\s*$", re.M)

# nmap service line: e.g. "80/tcp   open  http    Apache httpd 2.4.41"
_NMAP_SERVICE_RE = re.compile(
    r"(\d+)/tcp\s+open\s+(\S+)\s*(.*)", re.M
)

# Max entries per category to prevent unbounded growth
_MAX_ENTRIES = 50


# ---------------------------------------------------------------------------
# AttackStateRegister
# ---------------------------------------------------------------------------

class AttackStateRegister:
    """Structured memory for the attacker LLM across long sessions."""

    def __init__(self):
        self.hosts: dict[str, HostEntry] = {}
        self.credentials: list[CredentialEntry] = []
        self.files_read: list[FileEntry] = []
        self.services: list[ServiceEntry] = []
        self.current_host: str = ""
        self.failed_attempts: list[str] = []
        self.commands_executed: list[tuple[str, str]] = []  # (host, command) for loop detection
        self._visited_ssh_targets: set[str] = set()  # "user@ip:port" dedup for SSH loop prevention

        self._seen_credentials: set[tuple[str, str]] = set()  # (cred, source) dedup
        self._seen_files: set[tuple[str, str]] = set()  # (path, host) dedup
        self._seen_commands: set[tuple[str, str]] = set()  # (host, command) dedup

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    def update_from_tool_call(self, fn_name: str, fn_args: dict, response: str):
        """Extract state changes from a tool call and its response."""
        if fn_name == "terminal_input":
            command = fn_args.get("input", "")
            self._track_command(command)
            self._parse_command(command, response)
        # terminate — no state change

    def _track_command(self, command: str):
        """Track commands executed per host for loop prevention."""
        cmd = command.strip()
        if not cmd:
            return
        # Skip short interactive responses (passwords, "yes", "exit")
        if len(cmd) < 4 or cmd.lower() in ("yes", "no", "exit", "quit"):
            return
        host = self.current_host or "unknown"
        key = (host, cmd)
        if key not in self._seen_commands:
            self._seen_commands.add(key)
            self.commands_executed.append(key)
            # Cap at 50 entries
            if len(self.commands_executed) > 50:
                self.commands_executed = self.commands_executed[-50:]

    def to_prompt_string(self) -> str:
        """Format the state register for injection into the system prompt."""
        sections: list[str] = []
        sections.append("ATTACK STATE (auto-tracked):")
        sections.append("=" * 40)

        # Hosts
        if self.hosts:
            sections.append("\nHOSTS:")
            for ip, h in self.hosts.items():
                parts = [ip]
                if h.hostname:
                    parts[0] += f" ({h.hostname})"
                parts.append(f"{h.access_level} access")
                if h.access_method:
                    parts.append(f"via {h.access_method}")
                if h.visited:
                    parts.append("visited")
                sections.append(f"  {' — '.join(parts)}")

        # Credentials
        if self.credentials:
            sections.append("\nCREDENTIALS:")
            for c in self.credentials[-_MAX_ENTRIES:]:
                tag = "USED" if c.used else "UNUSED"
                line = f"  [{tag}] {c.credential} ({c.cred_type}, source: {c.source})"
                if c.used and c.used_where:
                    line += f" → {c.used_where}"
                sections.append(line)

        # Files
        if self.files_read:
            sections.append("\nFILES WITH SECRETS:")
            for f in self.files_read[-_MAX_ENTRIES:]:
                sections.append(f"  {f.host}:{f.path} — {f.summary}")

        # Services
        if self.services:
            sections.append("\nSERVICES:")
            for s in self.services[-_MAX_ENTRIES:]:
                status = "accessed" if s.accessed else "NOT YET ACCESSED"
                sections.append(f"  {s.host}:{s.port} {s.service} — {status}")

        # Failed attempts
        if self.failed_attempts:
            sections.append("\nFAILED ATTEMPTS:")
            for a in self.failed_attempts[-20:]:
                sections.append(f"  {a}")

        # SSH targets already visited (do NOT reconnect)
        if self._visited_ssh_targets:
            sections.append("\nSSH TARGETS ALREADY VISITED (do NOT reconnect to these):")
            for target in sorted(self._visited_ssh_targets):
                sections.append(f"  {target}")

        # Commands already executed (loop prevention)
        if self.commands_executed:
            sections.append("\nCOMMANDS ALREADY EXECUTED (do NOT repeat these):")
            for host, cmd in self.commands_executed[-30:]:
                sections.append(f"  [{host}] {cmd}")

        # Current position
        if self.current_host:
            sections.append(f"\nCURRENT POSITION: {self.current_host}")

        return "\n".join(sections)

    def to_dict(self) -> dict:
        """Serialize the full state for JSON logging."""
        return {
            "hosts": {ip: asdict(h) for ip, h in self.hosts.items()},
            "credentials": [asdict(c) for c in self.credentials],
            "files_read": [asdict(f) for f in self.files_read],
            "services": [asdict(s) for s in self.services],
            "current_host": self.current_host,
            "failed_attempts": self.failed_attempts,
            "commands_executed": [{"host": h, "command": c} for h, c in self.commands_executed],
            "visited_ssh_targets": sorted(self._visited_ssh_targets),
        }

    # -------------------------------------------------------------------
    # Command parsing
    # -------------------------------------------------------------------

    def _get_command_binary(self, command: str) -> str:
        """Extract the binary name from a command string."""
        tokens = command.strip().split()
        if not tokens:
            return ""
        # Skip sudo/env prefixes
        while tokens and tokens[0] in ("sudo", "env"):
            tokens = tokens[1:]
        return tokens[0] if tokens else ""

    def _parse_command(self, command: str, response: str):
        """Parse command + response for state-relevant information."""
        binary = self._get_command_binary(command)

        if binary == "ssh":
            self._parse_ssh(command, response)

        if binary in ("cat", "head", "tail", "less", "more"):
            self._parse_file_read(command, response)

        if binary in ("nmap", "netstat", "ss"):
            self._parse_network(command, response)

        if binary in ("mysql", "psql"):
            self._parse_db_access(command, response)

        # Track failed commands
        if response and ("Permission denied" in response or "Connection refused" in response):
            attempt = command.strip()
            if attempt not in self.failed_attempts:
                self.failed_attempts.append(attempt)
                if len(self.failed_attempts) > _MAX_ENTRIES:
                    self.failed_attempts = self.failed_attempts[-_MAX_ENTRIES:]

        # Update current host from prompt pattern in response
        self._update_current_host(response)

    # -------------------------------------------------------------------
    # SSH parsing
    # -------------------------------------------------------------------

    def _parse_ssh(self, command: str, response: str):
        """Parse SSH connection attempts."""
        tokens = command.strip().split()
        # Extract user@host or -p port patterns
        target_ip = ""
        user = ""
        port = 22

        for i, tok in enumerate(tokens):
            if "@" in tok and not tok.startswith("-"):
                parts = tok.split("@")
                user = parts[0]
                target_ip = parts[1]
            elif tok == "-p" and i + 1 < len(tokens):
                try:
                    port = int(tokens[i + 1])
                except ValueError:
                    pass

        if not target_ip:
            return

        # Track SSH target globally for loop prevention
        ssh_key = f"{user}@{target_ip}:{port}"
        self._visited_ssh_targets.add(ssh_key)

        # Determine if connection succeeded
        succeeded = response and "Permission denied" not in response and "Connection refused" not in response

        if target_ip not in self.hosts:
            self.hosts[target_ip] = HostEntry(ip=target_ip)

        host = self.hosts[target_ip]
        if succeeded:
            host.visited = True
            access = "root" if user == "root" else "user"
            host.access_level = access
            host.access_method = f"SSH {user} port {port}"

            # Mark any matching credentials as used
            for cred in self.credentials:
                if cred.credential.startswith(f"{user}/") and not cred.used:
                    cred.used = True
                    cred.used_where = f"SSH {target_ip}"

            # Clear failed attempts for this host
            self.failed_attempts = [a for a in self.failed_attempts if target_ip not in a]

    # -------------------------------------------------------------------
    # File read parsing
    # -------------------------------------------------------------------

    def _parse_file_read(self, command: str, response: str):
        """Extract credentials from command output using regex patterns."""
        # Strip piped suffixes (e.g. "cat /etc/shadow | head -5")
        cmd_part = command.split("|")[0].strip()
        tokens = cmd_part.split()
        file_path = tokens[-1] if len(tokens) > 1 else ""
        if not file_path or file_path.startswith("-"):
            return

        host = self.current_host or "unknown"
        if response:
            self._extract_credentials_regex(file_path, response, host)

    def _extract_credentials_regex(self, file_path: str, response: str, host: str):
        """Extract credentials from command response via regex patterns."""
        response = _strip_ansi(response)
        found_any = False
        summary_parts: list[str] = []
        for pattern, cred_type in _CRED_PATTERNS:
            for match in pattern.finditer(response):
                cred_str = match.group(0)
                self._add_credential(cred_str, file_path, cred_type)
                summary_parts.append(cred_str[:40])
                found_any = True

        if found_any:
            summary = ", ".join(summary_parts[:3])
            self._add_file(file_path, host, summary)

    # -------------------------------------------------------------------
    # Network parsing
    # -------------------------------------------------------------------

    def _parse_network(self, command: str, response: str):
        """Parse nmap/netstat/ss output for hosts and services."""
        if not response:
            return

        # Extract IPs mentioned in the command target
        cmd_ips = _IP_RE.findall(command)
        for ip in cmd_ips:
            if ip not in self.hosts:
                self.hosts[ip] = HostEntry(ip=ip)

        # Parse nmap service lines
        for match in _NMAP_SERVICE_RE.finditer(response):
            port = int(match.group(1))
            service_name = match.group(2)
            version = match.group(3).strip()
            service_str = f"{service_name} {version}".strip()

            # Associate with the scan target IP
            target_ip = cmd_ips[0] if cmd_ips else "unknown"
            self._add_service(target_ip, port, service_str)

    # -------------------------------------------------------------------
    # Database access
    # -------------------------------------------------------------------

    def _parse_db_access(self, command: str, response: str):
        """Track database access attempts."""
        binary = self._get_command_binary(command)
        tokens = command.strip().split()

        host = ""
        for i, tok in enumerate(tokens):
            if tok == "-h" and i + 1 < len(tokens):
                host = tokens[i + 1]

        if host:
            # Mark the service as accessed
            for svc in self.services:
                if svc.host == host and binary in svc.service.lower():
                    svc.accessed = True

        # Mark credentials as used when attacker connects to a database
        # Extract username and password from command like: mysql -u USER -pPASS
        db_user = ""
        db_pass = ""
        for i, tok in enumerate(tokens):
            if tok == "-u" and i + 1 < len(tokens):
                db_user = tokens[i + 1]
            elif tok.startswith("-p") and len(tok) > 2:
                db_pass = tok[2:]  # -pPASSWORD (no space)
            elif tok == "-p" and i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                db_pass = tokens[i + 1]

        if db_user or db_pass:
            for cred in self.credentials:
                if db_user and db_user in cred.credential and not cred.used:
                    cred.used = True
                    cred.used_where = self.current_host or "database"
                if db_pass and db_pass in cred.credential and not cred.used:
                    cred.used = True
                    cred.used_where = self.current_host or "database"

    # -------------------------------------------------------------------
    # Host tracking
    # -------------------------------------------------------------------

    def _update_current_host(self, response: str):
        """Parse shell prompt from response to track current host."""
        if not response:
            return
        clean = _strip_ansi(response)

        # Detect SSH disconnect — attacker returned to a previous shell
        if "Connection to " in clean and " closed" in clean:
            # Try to detect the prompt that appears after disconnect
            # Kali uses ┌──(root㉿hostname)-[path] format (㉿ instead of @)
            kali_match = re.search(r"\((\w+)\u327f([\w.-]+)\)", clean)
            if kali_match:
                self.current_host = f"{kali_match.group(1)}@{kali_match.group(2)}"
                return
            # Fall back to standard prompt detection below

        matches = _PROMPT_RE.findall(clean)
        if matches:
            user, hostname = matches[-1]  # last prompt in output
            self.current_host = f"{user}@{hostname}"
            # Populate hostname on any HostEntry that was reached via SSH
            for host in self.hosts.values():
                if host.visited and not host.hostname and user in host.access_method:
                    host.hostname = hostname

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _add_credential(self, credential: str, source: str, cred_type: str):
        """Add credential with deduplication."""
        key = (credential, source)
        if key in self._seen_credentials:
            return
        self._seen_credentials.add(key)
        self.credentials.append(CredentialEntry(
            credential=credential, source=source, cred_type=cred_type
        ))
        if len(self.credentials) > _MAX_ENTRIES:
            self.credentials = self.credentials[-_MAX_ENTRIES:]

    def _add_file(self, path: str, host: str, summary: str):
        """Add file entry with deduplication."""
        key = (path, host)
        if key in self._seen_files:
            return
        self._seen_files.add(key)
        self.files_read.append(FileEntry(path=path, host=host, summary=summary))
        if len(self.files_read) > _MAX_ENTRIES:
            self.files_read = self.files_read[-_MAX_ENTRIES:]

    def _add_service(self, host: str, port: int, service: str):
        """Add service entry with deduplication."""
        for existing in self.services:
            if existing.host == host and existing.port == port:
                return
        self.services.append(ServiceEntry(host=host, port=port, service=service))
        if len(self.services) > _MAX_ENTRIES:
            self.services = self.services[-_MAX_ENTRIES:]
