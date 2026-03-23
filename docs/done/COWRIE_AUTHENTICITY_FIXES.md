# Design: Cowrie Command Authenticity Fixes

## Problem Summary

Analysis of the `backup_server` profile against Cowrie's command handlers revealed that many commands an attacker will run produce output that contradicts the profile. The gaps fall into 3 categories:

1. **`ps` shows nothing from the profile** — the native `Command_ps` reads from `server.process` (loaded from `cmdoutput.json`), but `_write_cowrie_cfg` never sets `[shell] processes`. The profile converter writes a profile-aware `usr/bin/ps` txtcmd, but the native handler takes priority and the txtcmd is never reached.

2. **`crontab -l` always says "no crontab"** — hardcoded response, ignores profile `crontabs` field entirely.

3. **High-frequency attacker commands have no native handler** — `ss`, `systemctl`, `head`, `tail`, `grep` all fall to LLM fallback, which can't read the pickle filesystem and returns hallucinated output.

These issues affect ALL profiles, not just backup_server.

---

## Fix 1: Profile-Aware `ps` Output

**Root cause:** Dual-path conflict. `generate_txtcmds()` writes `usr/bin/ps` (profile-aware), but `Command_ps` in `base.py` is registered as `commands["ps"]` and takes priority in `getCommand()`. The native handler reads from `server.process`, which loads from `cmdoutput.json` via `[shell] processes` config — but this config key is never set by `_write_cowrie_cfg`.

**Fix:** Generate a profile-aware `cmdoutput.json` in `deploy_profile()` and point `[shell] processes` to it.

**File: `Reconfigurator/profile_converter.py`** — new function:

```python
def generate_cmdoutput(profile: dict, output_path: Path) -> None:
    """Generate cmdoutput.json for Cowrie's native ps handler."""
    _vsz_rss = {
        "apache2": (171680, 5244), "mysqld": (1793204, 178432),
        "sshd": (72304, 5520), "cron": (8544, 3200),
        "dockerd": (1564832, 89424), "nginx": (141456, 4892),
        "node_exporter": (24680, 8120), "rsyncd": (8840, 3400),
        "borg": (45200, 18900), "postfix": (82400, 6200),
    }

    ps_entries = []
    # Standard kernel/init entries
    ps_entries.append({
        "USER": "root", "PID": 1, "CPU": 0.0, "MEM": 0.4,
        "VSZ": 167340, "RSS": 11200, "TTY": "?", "STAT": "Ss",
        "START": "Jan01", "TIME": 0.48,
        "COMMAND": "/sbin/init"
    })

    # Profile services
    for svc in profile.get("services", []):
        svc_base = svc["name"].split("-")[0]
        vsz, rss = _vsz_rss.get(svc_base, (12345 + svc.get("pid", 1) * 7, 6789 + svc.get("pid", 1) * 3))
        mem_pct = round(rss / 4096000 * 100, 1)
        ps_entries.append({
            "USER": svc.get("user", "root"),
            "PID": svc.get("pid", 1),
            "CPU": 0.1,
            "MEM": mem_pct,
            "VSZ": vsz,
            "RSS": rss,
            "TTY": "?",
            "STAT": "Ss",
            "START": "Jan01",
            "TIME": 0.42,
            "COMMAND": svc.get("command", svc["name"])
        })

    cmdoutput = {"command": {"ps": ps_entries}}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cmdoutput, indent=2), encoding="utf-8")
```

Call from `deploy_profile()`:
```python
cmdoutput_path = cowrie_base / "share" / "cowrie" / "cmdoutput.json"
generate_cmdoutput(profile, cmdoutput_path)
```

**File: `main.py`** — in `_write_cowrie_cfg`, add:
```python
cfg.set("shell", "processes", "share/cowrie/cmdoutput.json")
```

This makes the native `Command_ps` read profile services. The txtcmd `usr/bin/ps` can remain as a fallback.

---

## Fix 2: Profile-Aware `crontab -l`

**Root cause:** `Command_crontab` in `crontab.py` hardcodes `"no crontab for {user}"` for `-l`. It never checks the profile's `crontabs` field.

**Fix:** Read crontabs from the profile, same pattern as `su.py`'s `_get_profile_users()`.

**File: `Cowrie/cowrie-src/src/cowrie/commands/crontab.py`**

```python
def _get_profile_crontabs(self) -> dict:
    """Get crontab entries from profile."""
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    if handler is None:
        return {}
    profile = getattr(handler, "_profile", {})
    return profile.get("crontabs", {})
```

Update the `-l` branch:
```python
elif opt == "-l":
    crontabs = self._get_profile_crontabs()
    user_crontab = crontabs.get(user, "")
    if user_crontab:
        self.write(user_crontab)
        if not user_crontab.endswith("\n"):
            self.write("\n")
    else:
        self.write(f"no crontab for {user}\n")
    self.exit()
    return
```

Also handle the case where the `crontabs` profile field uses the current user's name. Cowrie's `self.protocol.user.avatar.username` gives the logged-in user.

---

## Fix 3: Native `ss` Command Handler

**Why:** `ss -tlnp` is the modern replacement for `netstat -tlnp`. Most attackers use `ss` first. We already have a profile-aware `netstat` handler — `ss` should reuse the same data source.

**File:** `Cowrie/cowrie-src/src/cowrie/commands/ss.py` (new)

**Pattern:** Same as `netstat.py` — reads profile services, formats output.

**Supported flags:** `-t` (TCP), `-u` (UDP), `-l` (listening), `-n` (numeric), `-p` (processes), `-a` (all), `-4`/`-6`, `-h` (help)

**Output format (matches real `ss`)**:
```
Netid  State   Recv-Q  Send-Q   Local Address:Port    Peer Address:Port  Process
tcp    LISTEN  0       128      0.0.0.0:22            0.0.0.0:*          users:(("sshd",pid=892,fd=3))
tcp    LISTEN  0       128      0.0.0.0:873           0.0.0.0:*          users:(("rsync",pid=1678,fd=4))
```

Register as `commands["ss"]` and `commands["/usr/bin/ss"]`.

---

## Fix 4: Native `systemctl` Command Handler

**Why:** `systemctl status <service>` is the first recon command on any modern Linux system. bash_history in multiple profiles references it. Without a handler, LLM hallucinates output inconsistent with profile services.

**File:** `Cowrie/cowrie-src/src/cowrie/commands/systemctl.py` (new)

**Supported subcommands:**
- `status <service>` — check profile services list, show "active (running)" if found, "inactive (dead)" if not
- `list-units --type=service` — list all profile services
- `start/stop/restart/enable/disable <service>` — accept silently (honeypot shouldn't resist)
- `--version` — print systemd version string
- No args — show usage

**Key design:** Read services from `self.protocol.llm_fallback_handler._profile["services"]`. Match service name loosely (e.g., `systemctl status ssh` matches service named `sshd`).

**Output format for `status`** (matches real systemd):
```
● sshd.service - OpenBSD Secure Shell server
     Loaded: loaded (/lib/systemd/system/sshd.service; enabled)
     Active: active (running) since Mon 2026-02-24 08:00:00 UTC; 2 weeks ago
   Main PID: 892 (sshd)
      Tasks: 1 (limit: 4915)
     Memory: 5.4M
        CPU: 1.234s
     CGroup: /system.slice/sshd.service
             └─892 sshd: /usr/sbin/sshd -D
```

Register as `commands["systemctl"]` and `commands["/usr/bin/systemctl"]`.

---

## Fix 5: Filesystem-Aware `head` and `tail`

**Why:** `head` and `tail` are used constantly — `tail -f /var/log/backup.log`, `head -20 /etc/hosts`. Without native handlers, they fall to LLM which can't read the pickle filesystem. `cat` works perfectly because it has a native handler that reads from honeyfs/pickle. `head` and `tail` should do the same.

**File:** `Cowrie/cowrie-src/src/cowrie/commands/cat.py` — extend with `Command_head` and `Command_tail` classes, or create a new `headtail.py`.

**Pattern:** Same as `cat.py` — resolve file path, read from `self.fs` or honeyfs, then truncate output.

**`head` flags:** `-n N` (first N lines, default 10), `-c N` (first N bytes), `-q` (quiet)
**`tail` flags:** `-n N` (last N lines, default 10), `-c N` (last N bytes), `-f` (follow — print last lines then exit, since we can't actually follow)

**Key decision:** `tail -f` should print the last 10 lines and then hang (set `self.callbacks = [self._ignore_input]`) until Ctrl-C. This simulates the "follow" behavior without actually tailing. The attacker sees recent log entries and thinks it's live.

Register `head`/`tail` as both short name and `/usr/bin/head`, `/usr/bin/tail`.

---

## Fix 6: Filesystem-Aware `grep`

**Why:** `grep -r password /etc/` is one of the top 5 attacker commands. Without a native handler, the LLM can't search the actual pickle filesystem, so it hallucinates results. This is the single most dangerous gap for honeypot detection — if `grep` returns files that don't exist in `ls`, or misses files that do, the attacker knows something is wrong.

**File:** `Cowrie/cowrie-src/src/cowrie/commands/grep.py` (new)

**Pattern:** Walk the pickle filesystem + honeyfs, search file contents for the pattern, output matching lines.

**Supported flags:** `-i` (case insensitive), `-r`/`-R` (recursive), `-l` (files only), `-n` (line numbers), `-c` (count), `-v` (invert), `-H` (with filename), `-h` (no filename), `-e PATTERN`, `--include=GLOB`, `--exclude=GLOB`

**Key design:**
1. Resolve paths against `self.fs` (pickle filesystem)
2. For each file, check if content exists in honeyfs (real files on disk) — read via `self.protocol.getHoneyfsPath()` or similar
3. If no honeyfs file, check `file_contents` from the profile (via `llm_fallback_handler._profile`)
4. Apply pattern matching (Python `re` module)
5. Format output with filenames and line numbers

**Scope limit:** Don't support full regex — basic string matching + `-i` is enough. Full PCRE is overkill and risks edge-case bugs.

Register as `commands["grep"]`, `commands["/usr/bin/grep"]`, `commands["/bin/grep"]`.

---

## Fix 7: `df -h` from Profile

**Why:** `generate_txtcmds()` already writes a generic `usr/bin/df` txtcmd, but it's the same 50G/200G layout for every profile. The backup_server mail spool reveals 50G root + 500G /var/backups. These should be consistent.

**Fix:** Make `generate_txtcmds` read disk layout from the profile. Add an optional `disk_layout` field to the profile schema:

```json
"disk_layout": [
    {"filesystem": "/dev/sda1", "size": "50G", "used": "18G", "mount": "/"},
    {"filesystem": "/dev/sdb1", "size": "500G", "used": "312G", "mount": "/var/backups"}
]
```

If not present, fall back to the current generic layout. Update `generate_txtcmds` to use this field.

**Impact:** Low priority — attacker may not cross-reference `df` with mail contents. But it's a cheap fix.

---

## Implementation Priority

| # | Fix | Impact | Effort | Priority | Status |
|---|-----|--------|--------|----------|--------|
| 1 | Profile-aware `ps` (cmdoutput.json) | Critical | Low | **P0** | ✅ Done |
| 2 | Profile-aware `crontab -l` | Critical | Low | **P0** | ✅ Done |
| 3 | Native `ss` handler | High | Medium | **P1** | ✅ Done |
| 4 | Native `systemctl` handler | High | Medium | **P1** | ✅ Done |
| 5 | Filesystem-aware `head`/`tail` | High | Medium | **P1** | ✅ Done |
| 6 | Filesystem-aware `grep` | High | High | **P2** | ✅ Done |
| 7 | Profile-aware `df -h` | Medium | Low | **P2** | ✅ Done |
| 8 | `id` with group memberships | Medium | Low | **P2** | ✅ Done |
| 9 | `du -sh` filesystem-aware | Medium | Low | **P2** | ✅ Done |
| 10 | `service --status-all` from profile | Medium | Low | **P2** | ✅ Done |

**Suggested order:** 1 → 2 → 5 → 3 → 4 → 6 → 7 → 8 → 9 → 10

Fixes 1-2 are quick wins (modify existing code). Fix 5 is high value for low complexity (reuse `cat.py` pattern). Fixes 3-4 are new handlers but follow established patterns (like `netstat.py`). Fix 6 is the most complex due to recursive filesystem walking + content matching. Fixes 7-10 are polish.

---

## Fix 8: `id` with Group Memberships

**Root cause:** `Command_id` in `base.py` only shows primary UID/GID:
```
uid=0(root) gid=0(root) groups=0(root)
```

Profile users have rich group data (e.g., `backupadm` is in `backupadm` + `sudo`), but `id` ignores the `groups` field entirely.

**Fix:** Read the user's groups from the profile.

**File: `Cowrie/cowrie-src/src/cowrie/commands/base.py`** — modify `Command_id.call()`:

```python
class Command_id(HoneyPotCommand):
    def call(self) -> None:
        u = self.protocol.user
        username = u.username

        # Try to get group memberships from profile
        groups_str = f"{u.gid}({username})"
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler:
            profile = getattr(handler, "_profile", {})
            for pu in profile.get("users", []):
                if pu["name"] == username:
                    profile_groups = pu.get("groups", [])
                    if profile_groups:
                        # Map group names to GIDs (basic heuristic)
                        group_parts = []
                        for g in profile_groups:
                            if g == username:
                                group_parts.append(f"{u.gid}({g})")
                            elif g == "root":
                                group_parts.append(f"0({g})")
                            elif g == "sudo":
                                group_parts.append(f"27({g})")
                            elif g == "docker":
                                group_parts.append(f"999({g})")
                            elif g == "adm":
                                group_parts.append(f"4({g})")
                            else:
                                group_parts.append(f"{u.gid + 1}({g})")
                        groups_str = ",".join(group_parts)
                    break

        self.write(f"uid={u.uid}({username}) gid={u.gid}({username}) groups={groups_str}\n")
```

---

## Fix 9: `du -sh` Filesystem-Aware

**Root cause:** `Command_du` returns hardcoded `"28K ."` regardless of path or arguments.

**Fix:** Walk the pickle filesystem for the target directory, sum file sizes from the directory tree.

**File: `Cowrie/cowrie-src/src/cowrie/commands/du.py`** — modify `call()`:

```python
def call(self) -> None:
    # Parse args for -s (summary) and -h (human-readable)
    # Resolve target path against self.fs
    # Walk directory tree, sum sizes from pickle fs entries
    # Format with _human_readable() helper
    # If directory not found, error
```

Key method: use `self.fs.listdir(path)` to walk, and `self.fs.getfile(path)` to get size from the pickle entry's `A_SIZE` field.

Doesn't need to be perfect — just needs to return plausible sizes consistent with the file sizes in the profile's `directory_tree`.

---

## Fix 10: `service --status-all` from Profile

**Root cause:** `Command_service` in `service.py` has a hardcoded list of ~60 services. On a backup server, it shows Apache, MySQL, etc. — services that don't exist in the profile.

**Fix:** Read profile services and build the status list from them, supplemented with standard system services.

**File: `Cowrie/cowrie-src/src/cowrie/commands/service.py`** — modify the `--status-all` handler:

```python
def _get_status_all(self):
    # Always-present system services
    base_services = ["cron", "dbus", "rsyslog", "ssh"]

    # Profile services (always [+] running)
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    profile_services = []
    if handler:
        profile = getattr(handler, "_profile", {})
        for svc in profile.get("services", []):
            svc_name = svc["name"].split("-")[0]  # normalize
            profile_services.append(svc_name)

    running = set(base_services + profile_services)
    # Stopped services: plausible defaults minus running
    stopped = {"apache2", "bluetooth", "cups", "nfs-server"}
    stopped -= running

    lines = []
    for svc in sorted(running):
        lines.append(f" [ + ]  {svc}")
    for svc in sorted(stopped):
        lines.append(f" [ - ]  {svc}")
    return "\n".join(lines) + "\n"
```

---

## Additional Fixes: Skeleton Designs

### Fix 11: `journalctl` (P3 — low priority)

Only worth doing if LLM fallback proves inconsistent for it. A lightweight handler:

- `journalctl -u <service>` — check profile services, return a few template log lines with timestamps
- `journalctl --since today` — return recent-looking syslog entries
- No args — return last 10 generic journal lines

The profile already has `auth.log` and `backup.log` contents — `journalctl` could read those as source material.

### Fix 12: `docker` / `docker compose` (P3)

Only the most common subcommands:

- `docker ps` — read profile services, show containers for any service that looks Docker-based
- `docker images` — list plausible images based on profile services
- `docker compose ps` — similar to `docker ps`
- Everything else → LLM fallback

### Fix 13: Text editors `nano`/`vim` (P3)

Currently these hit LLM fallback, which is bad — an attacker who runs `vim /etc/hosts` gets hallucinated text instead of the actual file.

Simple fix: open the file via `self.fs.file_contents()`, display it, then enter a line-input mode that accepts `:q`, `:wq`, `:q!`, `Ctrl-X` (nano). Don't actually support editing — just show the file and let the attacker exit.

---

## What Stays as LLM Fallback (Acceptable)

These commands are uncommon enough or complex enough that LLM fallback is fine:

- `export` — already handled by Cowrie's shell parser (`KEY=VALUE` before commands sets env vars in `self.environ`)
- `source` — would need shell-level changes to execute file contents as commands; attacker can `cat` the file instead
- `less` / `more` — interactive pagers, extremely hard to emulate; attacker uses `cat` instead
- `chown` — modifying ownership in the pickle fs is cosmetic
- `restic`, `borg`, `rsync`, `aws`, `s3cmd`, `kubectl` — specialized tools, LLM handles these adequately since output format doesn't need to match exact filesystem state
- `openssl`, `certbot` — complex tool output, LLM is fine
- `postconf`, `postmap`, `postqueue`, `dovecot` — mail-specific tools, only relevant for mail_server profile
- `firewall-cmd` — CentOS/RHEL specific, `iptables` already has a handler
- `htop`, `top` — interactive TUI, txtcmd returns static snapshot (already exists)
- `jq` — JSON parsing tool, LLM handles this fine
