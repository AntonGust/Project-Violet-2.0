# Project Violet — System Summary

This document describes how Project Violet's custom Cowrie deployment differs from stock Cowrie, what commands are supported, and how the surrounding subsystems fit together.

---

## 1. High-Level Architecture

Project Violet is a closed-loop honeypot research platform with six subsystems:

```
┌──────────────┐   SSH    ┌──────────────────┐   LLM API   ┌─────────────┐
│  Sangria     │ ──────►  │  Cowrie Honeypot  │ ──────────► │  LLM        │
│  (Attacker)  │  via     │  (custom fork)    │  fallback   │  (GPT-4.1)  │
└──────┬───────┘  Kali    └────────┬──────────┘             └─────────────┘
       │                           │
       │ logs                      │ DB queries
       ▼                           ▼
┌──────────────┐          ┌──────────────────┐
│  Purple      │          │  Honeypot DB     │
│  (Metrics)   │          │  (MySQL/PG)      │
└──────────────┘          └──────────────────┘
       │
       │ entropy / coverage signals
       ▼
┌──────────────────────┐
│  Reconfigurator      │
│  (Profile Generator) │
└──────────────────────┘
```

| Subsystem | Directory | Purpose |
|-----------|-----------|---------|
| **Cowrie** | `Cowrie/cowrie-src/` | Modified medium-interaction SSH honeypot with LLM fallback, pre-query context injection, and database proxy |
| **Sangria** | `Sangria/` | LLM-driven autonomous attacker that SSHs into the honeypot via a Kali container, tags each command with MITRE ATT&CK tactics/techniques |
| **Purple** | `Purple/` | Post-session analysis: Shannon entropy, MITRE distribution heatmaps, tactic/technique sequences, session length statistics |
| **Reconfigurator** | `Reconfigurator/` | Generates new honeypot JSON profiles via LLM, validates novelty (Jaccard distance), converts profiles to Cowrie artifacts |
| **Blue Lagoon** | `Blue_Lagoon/` | Docker orchestration — builds/starts/stops Cowrie + DB containers, manages logs |
| **Utils** | `Utils/` | LLM client factory, experiment metadata |

### Docker Network Layout

All containers run on a bridge network `172.{RUNID}.0.0/24`:

| Container | IP | Port |
|-----------|----|------|
| Kali (attacker) | `172.{RUNID}.0.2` | Host: `30{RUNID}` → SSH 22 |
| Cowrie (honeypot) | `172.{RUNID}.0.3` | SSH 2222 |
| Honeypot DB | `172.{RUNID}.0.4` | MySQL 3306 / PostgreSQL 5432 |

---

## 2. Stock Cowrie vs. Custom Cowrie

| Feature | Stock Cowrie | Project Violet |
|---------|-------------|----------------|
| Unknown commands | Returns "command not found" | Routes to LLM fallback (GPT-4.1-mini) with session state and profile context |
| Filesystem identity | Static pickle, manually authored | Generated from JSON profile (`profile_converter.py`) |
| `netstat` output | Hardcoded SSH-only | Dynamically generated from profile services (Apache, MySQL, etc.) |
| `dpkg -l` output | Not implemented | Reads `installed_packages` from profile; install-detection overlay adds packages at runtime |
| `su` command | Mapped to no-op | Full implementation: `-`/`-l` login shell, `-c command`, user validation against profile |
| `sudo` command | Basic flag parsing | Fixed `-i`/`-s` as boolean flags, pipe chain propagation |
| `scp` command | Receive (`-t`) only | Added pull mode (`-f`) — serves files from virtual FS |
| Database commands | No database | Real MySQL/PostgreSQL container with profile-matched seed data; SQL queries executed via `db_proxy.py` |
| Session state | Stateless per command | `SessionStateRegister` tracks 50 entries with impact scoring across the session |
| Context injection | None | `prequery.py` maps 25+ command families to context types (packages, services, users, DB schema, cron, network) |
| Credential handling | Static `userdb.txt` | Generated from profile `ssh_config.accepted_passwords`; credential files protected from LLM leakage |
| Profile hot-reload | N/A | SIGUSR1 signal reloads profile JSON without restarting Cowrie |
| `env`/`printenv` | Minimal | Populated with `HOSTNAME`, `LANG`, `MAIL`, `PWD` |
| SSH keys | N/A | Realistic base64 Ed25519 key in honeyfs |
| txtcmds path | Built-in package only | Config-specified path checked first, then falls back to built-in |

---

## 3. Command Support

### 3.1 Native Python Commands (56 modules)

Full implementations with argument parsing, filesystem interaction, and in some cases profile awareness.

| Command | File | Notes |
|---------|------|-------|
| `adduser` | `adduser.py` | User creation |
| `apt` | `apt.py` | Debian package manager |
| `awk` | `awk.py` | Pattern processing |
| `base64` | `base64.py` | Encode/decode |
| `bash` | `bash.py` | Shell interpreter |
| `busybox` | `busybox.py` | Multi-call binary |
| `cat` | `cat.py` | File display (reads honeyfs + profile `file_contents`) |
| `chmod` | `chmod.py` | Permission changes |
| `chpasswd` | `chpasswd.py` | Password changes |
| `crontab` | `crontab.py` | Cron management |
| `curl` | `curl.py` | URL transfer |
| `cut` | `cut.py` | Line section removal |
| `dd` | `dd.py` | Block copy |
| `dig` | `dig.py` | DNS lookup |
| `dpkg` | `dpkg.py` | **Profile-aware** — reads `installed_packages`, runtime install overlay |
| `du` | `du.py` | Disk usage |
| `env` / `printenv` | `env.py` | Environment variables (aliased) |
| `ethtool` | `ethtool.py` | Ethernet settings |
| `find` | `find.py` | File search |
| `finger` | `finger.py` | User info |
| `free` | `free.py` | Memory usage |
| `fs` (cd, mkdir, etc.) | `fs.py` | Core filesystem operations |
| `ftpget` | `ftpget.py` | FTP retrieval |
| `gcc` | `gcc.py` | C compiler |
| `git` | `git.py` | Version control |
| `groups` | `groups.py` | Group membership |
| `ifconfig` | `ifconfig.py` | Network interfaces |
| `iptables` | `iptables.py` | Packet filtering |
| `last` | `last.py` | Login history |
| `locate` | `locate.py` | File search |
| `ls` | `ls.py` | **Profile-aware** — directory listing from virtual FS |
| `lspci` | `lspci.py` | PCI devices |
| `nc` | `nc.py` | Netcat |
| `netstat` | `netstat.py` | **Profile-aware** — dynamic service listings with `-p` PID/program |
| `nohup` | `nohup.py` | Hangup immunity |
| `perl` | `perl.py` | Perl interpreter |
| `ping` | `ping.py` | ICMP echo |
| `python` | `python.py` | Python interpreter |
| `scp` | `scp.py` | **Profile-aware** — `-t` receive + `-f` pull mode |
| `service` | `service.py` | Service management |
| `sleep` | `sleep.py` | Delay |
| `ssh` | `ssh.py` | **Profile-aware** — SSH client |
| `su` | `su.py` | **Profile-aware** — login shell, `-c`, user validation, nologin |
| `sudo` | `sudo.py` | **Profile-aware** — `-i`/`-s` flags, pipe propagation |
| `tar` | `tar.py` | Archive |
| `tee` | `tee.py` | Tee output |
| `tftp` | `tftp.py` | Trivial FTP |
| `ulimit` | `ulimit.py` | Resource limits |
| `uname` | `uname.py` | System info |
| `uniq` | `uniq.py` | Deduplication |
| `unzip` | `unzip.py` | ZIP extraction |
| `uptime` | `uptime.py` | Uptime display |
| `wc` | `wc.py` | Word/line count |
| `wget` | `wget.py` | Download |
| `which` | `which.py` | Command lookup |
| `yum` | `yum.py` | RedHat package manager |

### 3.2 Static Text Commands (txtcmds)

Pre-recorded outputs returned verbatim. Two layers: **built-in** (shipped with Cowrie source) and **profile-generated** (written by `profile_converter.py` to `cowrie_config/share/txtcmds/`).

**Built-in (22 files):**

| Path | Command |
|------|---------|
| `bin/df` | Disk usage |
| `bin/dmesg` | Boot messages |
| `bin/enable` | Shell built-in |
| `bin/mount` | Mount table |
| `bin/stty` | Terminal settings |
| `bin/sync` | Sync filesystems |
| `bin/ulimit` | Resource limits |
| `usr/bin/clear` | Clear screen |
| `usr/bin/emacs` | Editor stub |
| `usr/bin/getconf` | Config values |
| `usr/bin/killall` | Kill by name |
| `usr/bin/locate` | File search |
| `usr/bin/lscpu` | CPU info |
| `usr/bin/make` | Build tool |
| `usr/bin/nano` | Editor stub |
| `usr/bin/nproc` | CPU count |
| `usr/bin/pico` | Editor stub |
| `usr/bin/pkill` | Kill by pattern |
| `usr/bin/top` | Process monitor |
| `usr/bin/vi` | Editor stub |
| `usr/bin/vim` | Editor stub |
| `usr/sbin/vipw` | Password editor |

**Profile-generated (13 files):**

| Path | Command |
|------|---------|
| `usr/bin/arch` | Architecture |
| `usr/bin/df` | Disk usage (profile-specific) |
| `usr/bin/free` | Memory |
| `usr/bin/hostname` | Hostname |
| `usr/bin/id` | User identity |
| `usr/bin/last` | Login history |
| `usr/bin/netstat` | Network stats |
| `usr/bin/ps` | Process list |
| `usr/bin/uname` | System info |
| `usr/bin/uptime` | Uptime |
| `usr/bin/w` | Who is logged in |
| `usr/bin/whoami` | Current user |
| `usr/sbin/ifconfig` | Interface config |

### 3.3 LLM Fallback

Any command not handled by a Python module or txtcmd is routed to the LLM fallback (`llm_fallback.py`). This covers:

- `mysql`, `psql`, `mongosh` — database CLIs (with real query execution via `db_proxy.py`)
- `systemctl`, `journalctl` — systemd commands
- `docker`, `kubectl` — container orchestration
- `ssh-keygen`, `openssl` — crypto utilities
- `getent`, `id` (with arguments), `w` — user queries
- `ip`, `ss` — modern network commands
- Any other command the attacker tries

The fallback uses context from `prequery.py` (25+ command families mapped to profile sections) and the `SessionStateRegister` (up to 50 accumulated state entries with impact scores 0–4) to produce contextually accurate responses.

---

## 4. Recent Fixes (dbtest6 → dbtest7)

### 2026-02-25 — Honeypot Realism Fixes

| Fix | Severity | Details |
|-----|----------|---------|
| LLM model name in `cowrie.cfg` | Critical | `str(LLMModel.GPT_4_1_MINI)` produced the Python repr instead of `"gpt-4.1-mini"` — all fallback commands returned empty |
| txtcmds path resolution | High | Profile-generated txtcmds in config path were ignored; now checked first |
| `/etc/crontab` generation | Medium | `profile_converter.py` now generates crontab from profile data |
| `printenv` alias | Medium | Aliased to `env` handler |
| Session environment variables | Medium | `HOSTNAME`, `LANG`, `MAIL`, `PWD` populated |

### 2026-02-25b — Honeypot Detection Countermeasures

| Fix | Severity | Details |
|-----|----------|---------|
| Fake SSH key replaced | Critical | Literal `"fake_key_bytes_for_honeypot_simulation_only"` replaced with realistic Ed25519 data |
| `netstat` made profile-aware | Critical | Dynamic LISTEN lines from profile services instead of SSH-only |
| `sudo -i` flag parsing | High | `-i` and `-s` changed from argument-taking to boolean flags |
| `su` command implemented | High | Full `su` with login shell, `-c`, user validation, nologin handling |
| MySQL credential rejection | Medium | LLM now receives valid credentials from profile with "must succeed" instruction |

### 2026-03-01 — Fake Database Honeypot Service

| Fix | Severity | Details |
|-----|----------|---------|
| Real database container | Feature | Ephemeral MySQL 8.0 or PostgreSQL 16, auto-seeded from profile |
| `db_proxy.py` | Feature | Pure-Python database proxy (`pymysql`/`pg8000`), executes real SQL, caps at 100 rows |
| `db_seed_generator.py` | Feature | WordPress schema (~500 rows) for MySQL, business-app schema (~415 rows) for PostgreSQL |
| Version spoofing | Feature | Fixed internal image; version string spoofed to attacker via LLM layer |

---

## 5. Known Remaining Issues (from dbtest7)

From analysis of `dbtest7 attack_1` (109 commands):

| Issue | Commands Wasted | % of Session | Status |
|-------|----------------|--------------|--------|
| **File persistence across SSH sessions** | ~30 | 27% | Plan written (`docs/dbtest7_fix_plan.md` Fix 1). Each SSH session loads a fresh FS pickle; in-memory writes are discarded on disconnect. Fix: cache `CowrieServer` in `realm.py` so all sessions share one filesystem. |
| **Multiline shell input** (heredocs, quote continuation) | ~6 | 5% | Plan written (Fix 2). `lineReceived()` processes one line at a time with no continuation buffer. Fix: add `_line_buffer` and `_heredoc_delim` state to `HoneyPotShell`. |
| **SCP pull mode edge cases** | ~4 | 4% | Partially fixed (Fix 3). `-f` flag handling added but may have edge cases with directory pulls. |
| **Sudo + pipe filtering** | ~2 | 2% | Plan written (Fix 4). `sudo netstat | grep` doesn't chain the pipe — inner `PipeProtocol` doesn't propagate `next_command`. |

Session ended with `discovered honeypot: yes`, likely due to files disappearing between sessions.

---

## 6. Profile System

### What a Profile Is

A JSON file (schema: `Reconfigurator/RagData/filesystem_profile_schema.json`) that defines the complete identity of the honeypot server. Three pre-built profiles ship in `Reconfigurator/profiles/`:

| Profile | OS | Services | Theme |
|---------|----|----------|-------|
| `wordpress_server.json` | Ubuntu 20.04 | Apache, MySQL, SSH | WordPress production server |
| `database_server.json` | CentOS 7.9 | PostgreSQL, Nagios, SSH | Database server with replication |
| `cicd_runner.json` | Debian 12.4 | Jenkins, GitLab Runner, Docker, K8s | CI/CD build runner |

### Profile Contents

```
system        → hostname, OS, kernel, arch, timezone
users[]       → name, uid, gid, home, shell, password_hash, groups, sudo_rules
directory_tree → per-directory file listings with permissions, owners, sizes
file_contents  → full text of key files (passwd, shadow, wp-config.php, .env, scripts)
services[]    → name, pid, user, command, ports
network       → interfaces with IPs, MACs, netmasks
installed_packages[] → name + version
crontabs      → per-user crontab entries
ssh_config    → port, permit_root_login, banner, accepted_passwords
description   → human-readable summary
```

### How Profiles Become Cowrie Artifacts

`profile_converter.py` transforms a profile into:

| Artifact | Description |
|----------|-------------|
| `share/cowrie/fs.pickle` | Binary filesystem tree (50+ standard Linux dirs + profile entries) |
| `honeyfs/etc/passwd`, `shadow`, `group`, `hosts`, etc. | Readable file contents for `cat`/`head`/`tail` |
| `share/txtcmds/` | Static outputs for `uname`, `ps`, `ifconfig`, `df`, `free`, `whoami`, etc. |
| `etc/userdb.txt` | SSH login credentials |
| `etc/llm_prompt.txt` | System prompt for LLM fallback with OS/service/network context |
| `etc/profile.json` | Raw profile for runtime pre-query context |
| `etc/cowrie.cfg` overrides | hostname, kernel_version, arch |

### Lure Requirements

Profile generation enforces minimum lure counts:

| Category | Min | Examples |
|----------|-----|---------|
| Breadcrumb credentials | 4 | `.env`, `wp-config.php`, `.pgpass`, backup scripts |
| Lateral movement targets | 2 | `/etc/hosts` entries, SSH configs with internal IPs |
| Privilege escalation paths | 1 | Selective sudo, docker group, SUID binaries |
| Active system indicators | 3 | Log files, mail, `.bash_history`, `/tmp` artifacts |
| Explorable applications | 1 | WordPress, Docker Compose, `.git`, databases |
| Rabbit holes | 2 | Large files (>500 chars) that consume attacker iterations |

### Reconfiguration Flow

When Purple metrics detect behavioral stagnation (entropy plateau, MITRE coverage saturation):

1. `Reconfigurator` samples up to 5 previous profiles with session data
2. LLM generates a new profile JSON matching the schema
3. Profile validated against schema + lure requirements
4. Novelty checked via multi-dimensional Jaccard distance (threshold 0.4)
5. `profile_converter.py` generates new Cowrie artifacts
6. `db_seed_generator.py` creates new database init SQL
7. Cowrie container restarted with new identity

---

## 7. Key Files Reference

### Core Application

| File | Purpose |
|------|---------|
| `config.py` | Experiment configuration (models, providers, sessions, profile, reconfig method) |
| `main.py` | Orchestrates deploy → attack loop → reconfiguration |
| `main_menu.py` | Interactive CLI for experiment setup and data analysis |

### Cowrie Modifications

| File | Purpose |
|------|---------|
| `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py` | LLM fallback handler with `SessionStateRegister`, install detection, credential protection |
| `Cowrie/cowrie-src/src/cowrie/shell/prequery.py` | Context injection — maps 25+ command families to profile sections, budget-aware (3000 char max) |
| `Cowrie/cowrie-src/src/cowrie/shell/db_proxy.py` | Database proxy — executes real SQL against honeypot DB container |
| `Cowrie/cowrie-src/src/cowrie/shell/honeypot.py` | Modified shell — routes unknown commands to LLM fallback |
| `Cowrie/cowrie-src/src/cowrie/shell/protocol.py` | Fixed txtcmds path resolution |
| `Cowrie/cowrie-src/src/cowrie/commands/netstat.py` | Profile-aware service listings |
| `Cowrie/cowrie-src/src/cowrie/commands/sudo.py` | Fixed flag parsing, pipe chain propagation |
| `Cowrie/cowrie-src/src/cowrie/commands/su.py` | Full implementation with login shell and user validation |
| `Cowrie/cowrie-src/src/cowrie/commands/scp.py` | Added pull mode (`-f`) |
| `Cowrie/cowrie-src/src/cowrie/commands/dpkg.py` | Profile-aware package listing |

### Sangria (Attacker)

| File | Purpose |
|------|---------|
| `Sangria/sangria.py` | Main attack loop — LLM → tool call → terminal execution → log collection |
| `Sangria/attacker_prompt.py` | Builds attacker system prompt with MITRE guidance and target credentials |
| `Sangria/llm_tools.py` | Tool definitions (`terminal_input`, `terminate`) and handlers |
| `Sangria/terminal_io.py` | SSH/pexpect management to Kali container |
| `Sangria/log_extractor.py` | Reads new Cowrie JSON events since last offset |
| `Sangria/session_formatter.py` | Generates Markdown session reports |

### Reconfigurator

| File | Purpose |
|------|---------|
| `Reconfigurator/profile_converter.py` | Profile JSON → Cowrie artifacts (pickle, honeyfs, txtcmds, userdb, prompt) |
| `Reconfigurator/new_config_pipeline.py` | LLM-driven profile generation with schema validation and lure enforcement |
| `Reconfigurator/profile_distance.py` | Multi-dimensional Jaccard novelty check |
| `Reconfigurator/db_seed_generator.py` | Profile → database init SQL (WordPress/business schemas) |
| `Reconfigurator/profiles/` | Pre-built profile JSONs |
| `Reconfigurator/RagData/filesystem_profile_schema.json` | JSON schema for profiles |

### Purple (Metrics)

| File | Purpose |
|------|---------|
| `Purple/metrics/entropy.py` | Shannon entropy of tactic/technique distributions |
| `Purple/metrics/mitre_distribution.py` | MITRE coverage analysis, cumulative discovery, heatmaps |
| `Purple/metrics/sequences.py` | Tactic/technique/command sequence extraction |
| `Purple/metrics/session_length.py` | Session duration statistics |
| `Purple/stats_utils.py` | Distribution comparison, outlier detection, normalization |
| `Purple/RagData/retrive_techniques.py` | MITRE ATT&CK data loader (enterprise-attack.json) |

### Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Kali + Cowrie service definitions |
| `docker-compose.override.yml` | Generated — adds honeypot DB service |
| `cowrie_image/Dockerfile` | Multi-stage build: debian builder → distroless runtime |
| `Blue_Lagoon/honeypot_tools.py` | Docker orchestration, log management, DB compose generation |
| `Utils/llm_client.py` | OpenAI-compatible client factory with provider routing |
| `Utils/meta.py` | Experiment folder creation and metadata |
