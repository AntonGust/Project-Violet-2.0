# Design: P3 Command Handlers — journalctl, docker, nano/vim

## Context

These three commands were deferred as P3 in the original authenticity fixes plan. After analysis:

- **journalctl** — referenced in 10/13 profiles' bash_history. LLM fallback gets `services_detail` pre-query context but can't read actual log files from honeyfs. Output is non-deterministic between sessions.
- **docker** — referenced in 8/13 profiles. LLM fallback gets `container_context` (fake containers, ports, volumes, explicit "MUST succeed" instruction). Works decently but `docker ps` output varies between invocations.
- **vim/nano** — `vim` in 3 profiles' bash_history (editing config files like `/etc/postfix/main.cf`). LLM **cannot simulate an interactive editor** — it just returns hallucinated text. This is the biggest detection risk of the three.

---

## Fix 11: Native `journalctl` Handler

**Priority reassessment:** P2 (upgraded from P3 — 10/13 profiles reference it)

**Why native instead of LLM?** The LLM produces plausible-looking journal entries but they're inconsistent across sessions. A native handler can generate deterministic entries that match profile services and log file contents.

### Supported subcommands

| Usage | Behavior |
|-------|----------|
| `journalctl -u <service>` | Show log entries for service from profile |
| `journalctl -u <service> -f` | Show last entries, then hang until Ctrl-C |
| `journalctl --since "1 hour ago"` / `--since today` | Show recent-looking entries |
| `journalctl -xe` | Show last 20 entries with explanations |
| `journalctl` (no args) | Show last 10 generic syslog-style entries |
| `journalctl --disk-usage` | Show "Archived and active journals take up 48.0M in the file system." |

### Data sources

1. **Profile `file_contents`** — many profiles have `/var/log/auth.log`, `/var/log/backup.log`, `/var/log/syslog` with real-looking content. Parse these for journal output.
2. **Profile `services`** — generate service-specific log lines using templates:
   ```
   -- Journal begins at Mon 2026-01-27 08:00:00 UTC. --
   Feb 24 08:00:01 {hostname} {service}[{pid}]: Started {service}.
   Feb 24 08:00:02 {hostname} {service}[{pid}]: Listening on {port}
   ```
3. **Fallback** — if no matching log content or service, show generic systemd entries.

### Design

```python
class Command_journalctl(HoneyPotCommand):
    def start(self) -> None:
        # Parse args: -u <unit>, -f (follow), -xe, --since, -n <lines>, --disk-usage
        # ...

    def _get_service_logs(self, unit_name: str) -> list[str]:
        """Try sources in order:
        1. honeyfs log files matching the service (e.g., /var/log/backup.log for borgbackup)
        2. Generated template entries from profile services list
        """

    def _generate_template_entries(self, svc: dict, count: int = 10) -> list[str]:
        """Generate plausible journal entries for a service."""
        # Templates per service type:
        # sshd: "Accepted publickey for {user} from {ip}"
        # cron: "pam_unix(cron:session): session opened for user root"
        # nginx: "start worker process {pid}"
        # borg: "Repository /home/borguser/repos: Compacting segments"
        # generic: "Started {name}.", "Listening on port {port}"
```

### Log file mapping

To find relevant honeyfs content for a service:

```python
_SERVICE_LOG_MAP = {
    "sshd": ["/var/log/auth.log"],
    "cron": ["/var/log/syslog"],
    "borg": ["/var/log/backup.log"],
    "borgbackup": ["/var/log/backup.log"],
    "rsync": ["/var/log/backup.log", "/var/log/rsyncd.log"],
    "postfix": ["/var/log/mail.log"],
    "dovecot": ["/var/log/mail.log"],
    "nginx": ["/var/log/nginx/access.log", "/var/log/nginx/error.log"],
    "apache2": ["/var/log/apache2/access.log", "/var/log/apache2/error.log"],
    "named": ["/var/log/named/queries.log"],
    "mysql": ["/var/log/mysql/error.log"],
    "docker": ["/var/log/docker.log"],
}
```

Read from honeyfs first (real file content), then fall through to templates.

### `--since` handling

Don't actually parse time — just control how many entries to show:
- `--since today` → last 20 entries
- `--since "1 hour ago"` → last 10 entries
- `--since "5 minutes ago"` → last 3 entries

### `-f` (follow) behavior

Same as `tail -f` in our `head.py`: print entries, then hang with `self.callbacks` until Ctrl-C.

---

## Fix 12: Native `docker` Handler

**Priority reassessment:** P2 (upgraded — 8/13 profiles, and `docker ps` is one of the first recon commands)

**Why native instead of LLM?** The LLM fallback already works well for docker thanks to `container_context` pre-query injection. The risk is **inconsistency** — `docker ps` returns different container IDs and uptimes each time. A native handler makes it deterministic.

### Supported subcommands

| Usage | Behavior |
|-------|----------|
| `docker ps` / `docker ps -a` | List containers from profile |
| `docker images` | List images from profile containers |
| `docker logs <container>` | Show service-appropriate log lines |
| `docker inspect <container>` | Return JSON with realistic fields |
| `docker compose ps` / `docker-compose ps` | Same as `docker ps` filtered to compose project |
| `docker exec -it <c> /bin/bash` | **Delegate to LLM** — too complex to simulate |
| `docker node ls` / `docker service ls` | Swarm commands from profile |
| Everything else | **Delegate to LLM fallback** |

### Data source: profile `containers` field

Currently, container data is generated in `prequery.py`'s `_build_container_context()`. We need to either:

**Option A**: Generate `containers` in `profile_converter.py` and store in the profile JSON at deploy time (like `cmdoutput.json` for `ps`).

**Option B**: Read the profile `services` list at runtime and derive containers.

**Recommendation: Option A.** Generate a `containers.json` artifact during `deploy_profile()`. This way the native handler reads a static file, and output is identical every time.

### `containers.json` format

```json
[
  {
    "id": "a1b2c3d4e5f6",
    "name": "nginx-proxy",
    "image": "nginx:1.25-alpine",
    "status": "Up 47 days",
    "ports": "0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp",
    "created": "2026-01-27T08:00:00Z"
  }
]
```

Generated from profile `services` that look container-ish (have `container_image` field, or are in a `docker_swarm`/`monitoring_stack`/`dev_workstation` profile).

### Scope boundary

Only the read-only subcommands get native handling. Anything mutating (`docker run`, `docker exec`, `docker pull`, `docker build`) stays with LLM fallback, which already handles these well via `container_context`.

### `docker-compose` / `docker compose`

Register both `docker-compose` (old binary) and `docker` (new subcommand). When args start with `compose`, delegate to the compose handler path.

---

## Fix 13: Native `vim`/`nano` Editor Simulation

**Priority reassessment:** P1 (upgraded from P3 — this is the **highest detection risk** of the three. An attacker running `vim /etc/postfix/main.cf` who gets hallucinated text instead of the actual file contents will immediately know something is wrong.)

**Why this is critical:** Unlike journalctl/docker where the LLM produces plausible output, for editors the LLM cannot:
1. Show the actual file contents from honeyfs
2. Simulate cursor movement or interactive editing
3. Handle `:q`, `:wq`, `Ctrl-X` exit sequences

### Approach: Read-only editor simulation

We don't need a full editor. Attackers use `vim`/`nano` to **read** config files (credential hunting) and occasionally **write** small changes. The simulation:

1. **Open**: Display the file contents from honeyfs (same as `cat` but formatted like the editor)
2. **Interact**: Accept keystrokes but don't modify the buffer
3. **Exit**: Respond to `:q`, `:wq`, `:q!`, `ZZ` (vim) or `Ctrl-X` (nano)
4. **Write**: On `:w`/`:wq`/`Ctrl-O` — silently accept (attacker thinks file was saved)

### Vim design

```python
class Command_vim(HoneyPotCommand):
    def start(self) -> None:
        if not self.args:
            # No file — show vim splash screen, wait for :q
            self._show_splash()
            self.callbacks = [self._handle_vim_input]
            return

        filepath = self.args[-1]  # Last arg is the file (skip flags like -R)
        resolved = self.fs.resolve_path(filepath, self.protocol.cwd)

        if self.fs.isdir(resolved):
            self.errorWrite(f"\"{filepath}\" is a directory\n")
            self.exit()
            return

        try:
            contents = self.fs.file_contents(resolved)
            self._display_vim(contents.decode("utf-8", errors="replace"), filepath)
        except (FileNotFound, FileNotFoundError):
            # New file — show empty buffer with "[New File]"
            self._display_vim("", filepath, new_file=True)

        self.callbacks = [self._handle_vim_input]

    def _display_vim(self, text: str, filename: str, new_file: bool = False) -> None:
        """Show file in vim-like format with ~ for empty lines."""
        lines = text.split("\n")
        term_height = int(self.environ.get("LINES", 24)) - 2  # Status + cmd line
        for line in lines[:term_height]:
            self.write(line + "\n")
        # Fill remaining with ~
        remaining = term_height - min(len(lines), term_height)
        for _ in range(remaining):
            self.write("~\n")
        # Status line
        if new_file:
            self.write(f"\"{filename}\" [New File]\n")
        else:
            line_count = len(lines)
            char_count = len(text)
            self.write(f"\"{filename}\" {line_count}L, {char_count}C\n")

    def _handle_vim_input(self, line: str) -> None:
        """Handle vim command-mode input."""
        stripped = line.strip()
        if stripped in (":q", ":q!", ":wq", ":wq!", ":x", "ZZ", ":qa", ":qa!"):
            self.exit()
            return
        if stripped == ":w":
            self.write("\"...\" written\n")
            self.callbacks = [self._handle_vim_input]
            return
        # Anything else — stay in the editor
        self.callbacks = [self._handle_vim_input]

    def lineReceived(self, line: str) -> None:
        if self.callbacks:
            self.callbacks.pop(0)(line)
```

### Nano design

Simpler than vim — nano shows a header bar and footer with keybindings:

```python
class Command_nano(HoneyPotCommand):
    def start(self) -> None:
        filepath = self.args[-1] if self.args else ""
        # Display: header, file contents, footer with ^X ^O ^W etc.

    def _display_nano(self, text: str, filename: str) -> None:
        self.write(f"  GNU nano 5.4          {filename}\n\n")
        lines = text.split("\n")
        term_height = int(self.environ.get("LINES", 24)) - 5
        for line in lines[:term_height]:
            self.write(line + "\n")
        self.write("\n")
        self.write("^G Get Help  ^O Write Out  ^W Where Is  ^K Cut Text\n")
        self.write("^X Exit      ^R Read File  ^J Justify   ^U Paste Text\n")

    def handle_CTRL_X(self) -> None:
        self.exit()
```

### Key detail: `lineReceived` vs terminal raw mode

Cowrie operates in **line mode** (not raw char-by-char). This means:
- Vim's normal mode (single-key commands like `j`, `k`, `dd`) won't work — the user must press Enter
- This is acceptable because Cowrie's SSH transport already works this way for all commands
- The attacker types `:q` + Enter, which is the normal way to exit vim via command mode

For nano, `Ctrl-X` is already handled by Cowrie's `handle_CTRL_X()` method on the command class.

### File path handling

Both editors should handle:
- Absolute paths: `vim /etc/hosts`
- Relative paths: `vim ../config`
- Flags before filename: `vim -R /etc/shadow` (ignore `-R`, use last non-flag arg)
- `sudoedit` / `sudo vim`: already handled by Cowrie's sudo → vim pipeline

---

## Implementation Priority (revised)

| # | Fix | Impact | Effort | Priority |
|---|-----|--------|--------|----------|
| 13 | vim/nano editor simulation | **Critical** | Medium | **P1** |
| 11 | journalctl handler | High | Medium | **P2** |
| 12 | docker handler | Medium | High | **P2** |

**Suggested order:** 13 → 11 → 12

Fix 13 (editors) first because it's the highest detection risk — LLM cannot simulate editors at all. Fix 11 (journalctl) next because it's referenced in nearly every profile. Fix 12 (docker) last because the LLM fallback already handles it well via `container_context`.

---

## What stays with LLM fallback

Even with native handlers, these subcommands should fall through to LLM:

- `docker exec -it <container> /bin/bash` — needs shell-in-shell simulation
- `docker build` — complex multi-step output
- `docker run` — same as exec
- `journalctl` with complex filters (`--grep`, `--output=json`) — rare, LLM handles fine
- Vim/nano actual editing — we show the file, accept exit commands, but don't simulate insert mode buffer editing
