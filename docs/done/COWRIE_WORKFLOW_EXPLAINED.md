# How Cowrie Works in Project Violet — Full Workflow

This document explains every component of the Cowrie honeypot system in Project Violet, from JSON profile to attacker interaction, step by step.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [The Profile — Where It All Starts](#2-the-profile--where-it-all-starts)
3. [Lure Enrichment](#3-lure-enrichment)
4. [Profile Conversion — JSON to Cowrie Artifacts](#4-profile-conversion--json-to-cowrie-artifacts)
5. [Cowrie Configuration (cowrie.cfg)](#5-cowrie-configuration-cowriecfg)
6. [Docker Deployment](#6-docker-deployment)
7. [Inside Cowrie — How Commands Are Handled](#7-inside-cowrie--how-commands-are-handled)
8. [The Hybrid LLM Fallback System](#8-the-hybrid-llm-fallback-system)
9. [Sangria — The Attacker Simulation](#9-sangria--the-attacker-simulation)
10. [Log Extraction and Feedback Loop](#10-log-extraction-and-feedback-loop)
11. [Reconfiguration Loop](#11-reconfiguration-loop)
12. [HoneyNet Mode — Multi-Hop Chains](#12-honeynet-mode--multi-hop-chains)
13. [End-to-End Flow Diagram](#13-end-to-end-flow-diagram)

---

## 1. Architecture Overview

Project Violet is a research platform that runs LLM-augmented SSH honeypots (Cowrie) against LLM-driven attackers (Sangria). The system operates on Docker, with isolated networks connecting:

- **Kali container** — The attacker's machine, where Sangria sends SSH commands
- **Cowrie container(s)** — The honeypot(s), accepting SSH connections and simulating a real server
- **Database container** (optional) — A real MySQL/PostgreSQL instance for database honeypot scenarios

The key insight: Cowrie doesn't know every command an attacker might run. Project Violet extends Cowrie with a **hybrid LLM fallback** — unknown commands are forwarded to an LLM that generates realistic responses based on the server's profile.

### Key Directories

```
project-violet/
├── Reconfigurator/          # Profile generation, conversion, enrichment
│   ├── profiles/            # JSON profiles (the "blueprints" for honeypots)
│   ├── profile_converter.py # Converts JSON → Cowrie artifacts
│   ├── lure_agent.py        # LLM-based lure enrichment
│   └── new_config_pipeline.py # New profile generation via LLM
├── Blue_Lagoon/             # Docker orchestration
│   ├── honeypot_tools.py    # Start/stop containers, log reading
│   ├── compose_generator.py # HoneyNet compose file generation
│   └── credential_chain.py  # Multi-hop credential/breadcrumb injection
├── Sangria/                 # Attacker simulation
│   ├── sangria.py           # Main attack loop
│   ├── attacker_prompt.py   # LLM system prompt for the attacker
│   ├── terminal_io.py       # SSH terminal I/O with Kali
│   └── log_extractor.py     # Reads Cowrie JSON logs
├── Cowrie/cowrie-src/       # Modified Cowrie source
│   └── src/cowrie/
│       ├── commands/        # 60 built-in command handlers
│       ├── shell/           # Shell protocol + LLM fallback
│       ├── ssh/             # SSH protocol layer
│       └── llm/             # LLM client library
├── Purple/                  # Analysis and metrics
├── cowrie_config/           # Deployed Cowrie artifacts (generated at runtime)
├── config.py                # Experiment configuration
├── main.py                  # Experiment orchestrator
└── demo.py                  # Demo mode runner
```

---

## 2. The Profile — Where It All Starts

A **profile** is a JSON file that describes the server the honeypot will impersonate. It lives in `Reconfigurator/profiles/` (e.g., `wordpress_server.json`).

### Profile Structure

```json
{
  "id": "wordpress_server",
  "system": {
    "os": "Ubuntu 22.04.3 LTS",
    "hostname": "wp-prod-01",
    "kernel_version": "5.15.0-88-generic",
    "arch": "x86_64",
    "timezone": "UTC"
  },
  "users": [
    {
      "name": "root",
      "uid": 0, "gid": 0,
      "home": "/root",
      "shell": "/bin/bash",
      "password_hash": "$6$...",
      "groups": ["root"],
      "sudo_rules": ["ALL=(ALL:ALL) ALL"]
    },
    {
      "name": "www-data",
      "uid": 33, "gid": 33,
      "home": "/var/www",
      "shell": "/usr/sbin/nologin",
      "password_hash": "*"
    }
  ],
  "services": [
    { "name": "nginx", "ports": [80, 443], "user": "www-data", "pid": 1234 },
    { "name": "mysql", "ports": [3306], "user": "mysql", "pid": 5678 }
  ],
  "network": [
    { "interface": "eth0", "ip": "10.0.1.50", "netmask": "255.255.255.0", "mac": "02:42:ac:..." }
  ],
  "file_contents": {
    "/var/www/html/wp-config.php": "<?php\ndefine('DB_NAME', 'wordpress');\n...",
    "/root/.bash_history": "mysql -u root -p\nwp plugin list\n...",
    "/root/.ssh/id_rsa": "-----BEGIN RSA PRIVATE KEY-----\n..."
  },
  "directory_tree": {
    "/var/www/html": [
      { "name": "wp-config.php", "type": "file", "permissions": "0644", "owner": "www-data" },
      { "name": "wp-content", "type": "dir", "permissions": "0755", "owner": "www-data" }
    ]
  },
  "installed_packages": ["nginx", "php8.1", "mysql-server"],
  "crontabs": [
    { "user": "root", "schedule": "0 2 * * *", "command": "/usr/local/bin/backup.sh" }
  ],
  "ssh_config": {
    "accepted_passwords": {
      "root": ["toor", "wordpress123"],
      "deploy": ["deploy2024"]
    }
  },
  "lures": {
    "breadcrumb_credentials": [...],
    "lateral_movement_targets": [...],
    "privilege_escalation_paths": [...],
    "explorable_applications": [...],
    "rabbit_holes": [...]
  }
}
```

The profile describes **everything** about the fake server: what files exist, what services are running, what users are present, what the attacker will find when they poke around.

---

## 3. Lure Enrichment

Before deployment, the profile is enriched with **lures** — planted breadcrumbs that tempt attackers into specific behaviors.

**File:** `Reconfigurator/lure_agent.py`
**Entry point:** `enrich_lures(profile) -> (enriched_profile, lure_chains)`

### The 10 Lure Categories

| Category | What It Plants | Min Count |
|----------|---------------|-----------|
| breadcrumb_credentials | Passwords in .env, configs, history files | 3 |
| lateral_movement_targets | IPs/hostnames of "other servers" | 2 |
| privilege_escalation_paths | SUID binaries, writable sudoers | 2 |
| active_system_indicators | Running processes, recent logs, cron jobs | 2 |
| explorable_applications | Web apps, config files to investigate | 2 |
| rabbit_holes | Fake interesting paths that waste attacker time | 2 |
| cloud_credentials | AWS keys, GCP tokens in config files | 1 |
| container_escape_paths | Docker sockets, mounted volumes | 1 |
| cicd_tokens | Jenkins, GitLab CI tokens | 1 |
| supply_chain_artifacts | Package manifests, build scripts | 1 |

### How It Works

1. **Gap analysis** — Checks which lure categories are unsatisfied in the current profile
2. **LLM generation** — For each gap, queries the LLM to generate realistic credential files, config snippets, and directory entries that fit the server's theme
3. **Merge** — Adds the generated `file_contents`, `directory_tree`, `installed_packages`, and `users` to the profile without duplicating existing entries
4. **Lure chains** — Also generates multi-step "attack paths" (e.g., find SSH key → discover internal server → pivot) stored as metadata

---

## 4. Profile Conversion — JSON to Cowrie Artifacts

The profile converter transforms a JSON profile into the 6 artifacts Cowrie needs to function.

**File:** `Reconfigurator/profile_converter.py`
**Entry point:** `deploy_profile(profile, cowrie_base_path)`

### Artifact 1: fs.pickle — The Virtual Filesystem

Cowrie's filesystem is a serialized Python data structure. Each file/directory is stored as a list with 10 fields:

```
[A_NAME, A_TYPE, A_UID, A_GID, A_SIZE, A_MODE, A_CTIME, A_CONTENTS, A_TARGET, A_REALFILE]
  0       1       2      3       4       5       6         7           8         9
```

**What `profile_to_pickle()` does:**
1. Creates a skeleton of 100+ standard Linux directories (`/bin`, `/usr/lib`, `/var/log`, etc.)
2. Sets correct ownership (root:root, www-data:www-data) and permissions
3. Adds SUID bits on standard binaries (`/usr/bin/passwd`, `/bin/su`)
4. Inserts all directories and files from `directory_tree`
5. Generates realistic timestamps (install date ~90 days ago, recent files within 7 days)
6. Serializes as a pickle file

**Output:** `cowrie_config/share/fs.pickle`

### Artifact 2: honeyfs/ — Readable File Contents

When an attacker runs `cat /etc/passwd`, Cowrie needs actual file content to return. The honeyfs directory mirrors the virtual filesystem with real file contents.

**What `generate_honeyfs()` creates:**
- `/etc/passwd`, `/etc/shadow`, `/etc/group` — Generated from profile users
- `/etc/hosts`, `/etc/resolv.conf`, `/etc/fstab` — System files
- `/etc/ssh/sshd_config` — Realistic SSH configuration
- `/etc/systemd/system/*.service` — Systemd units from profile services
- `/etc/crontab` — From profile crontabs
- All `file_contents` from the profile (wp-config.php, .env, SSH keys, etc.)
- User home directories with `.bashrc`, `.profile`

**Output:** `cowrie_config/honeyfs/`

### Artifact 3: txtcmds/ — Static Command Outputs

For commands whose output should be consistent and fast (no LLM call needed), the converter generates pre-baked output files.

**What `generate_txtcmds()` creates:**
| Command | What It Generates |
|---------|------------------|
| `uname -a` | Linux kernel string matching profile |
| `whoami` | "root" |
| `id` | uid/gid/groups from profile |
| `hostname` | From profile system.hostname |
| `uptime` | Realistic uptime string |
| `ps aux` | Process list from profile services with realistic VSZ/RSS |
| `ifconfig` | Network interfaces from profile |
| `netstat -tlnp` | Listening ports from profile services |
| `df -h` | Disk usage |
| `free -m` | Memory usage |
| `last` | Login history |
| `w` | Active users |

**Output:** `cowrie_config/share/txtcmds/` (e.g., `txtcmds/usr/bin/uname`)

### Artifact 4: userdb.txt — SSH Credentials

Cowrie uses a flat file to decide which username/password combinations to accept.

**Format:** `username:uid:password`

```
root:0:toor
root:0:wordpress123
deploy:1001:deploy2024
```

Pulled from `profile.ssh_config.accepted_passwords`.

**Output:** `cowrie_config/etc/userdb.txt`

### Artifact 5: llm_prompt.txt — LLM System Prompt

When Cowrie's hybrid LLM fallback handles an unknown command, it needs context about what server it's impersonating.

**Contains:**
- System info (OS, arch, hostname)
- Running services and their ports
- Network interfaces
- Users with their roles
- Database version context (for spoofing MySQL/PostgreSQL versions)
- Rules: "You are simulating this server. Respond as the real server would."

**Output:** `cowrie_config/etc/llm_prompt.txt`

### Artifact 6: profile.json — Full Profile for Runtime

The complete profile JSON is also stored for the LLM fallback's pre-query context system.

**Output:** `cowrie_config/etc/profile.json`

---

## 5. Cowrie Configuration (cowrie.cfg)

The `deploy_cowrie_config()` function in `main.py` writes a customized `cowrie.cfg`:

```ini
[honeypot]
hostname = wp-prod-01
log_path = /cowrie/cowrie-git/var/log/cowrie
contents_path = /cowrie/cowrie-git/honeyfs
txtcmds_path = /cowrie/cowrie-git/share/cowrie/txtcmds

[shell]
filesystem = /cowrie/cowrie-git/share/cowrie/fs.pickle
kernel_version = 5.15.0-88-generic
arch = x86_64
hardware_platform = x86_64
operating_system = GNU/Linux

[ssh]
listen_endpoints = tcp:2222:interface=0.0.0.0

[output_jsonlog]
enabled = true
logfile = /cowrie/cowrie-git/var/log/cowrie/cowrie.json

[hybrid_llm]
enabled = true
api_key = <from env COWRIE_HYBRID_LLM_API_KEY>
model = gpt-4.1-mini
host = https://api.openai.com
path = /v1/chat/completions
max_tokens = 500
temperature = 0.3
prompt_file = /cowrie/cowrie-git/etc/llm_prompt.txt
profile_file = /cowrie/cowrie-git/etc/profile.json
```

---

## 6. Docker Deployment

### Single-Pot Mode

**File:** `docker-compose.yml`

```
                    Docker Bridge Network (172.{RUNID}.0.0/24)
                    ┌──────────────────────────────────┐
                    │                                  │
              ┌─────┴─────┐                    ┌───────┴──────┐
              │   Kali    │                    │   Cowrie     │
              │ .0.2      │ ──── SSH ────────> │ .0.3         │
              │ port 3022 │                    │ port 2222    │
              └───────────┘                    └──────────────┘
```

**Volumes mounted into Cowrie:**
- `./cowrie_config/etc` → `/cowrie/cowrie-git/etc` (config + credentials)
- `./cowrie_config/honeyfs` → `/cowrie/cowrie-git/honeyfs` (file contents)
- `./cowrie_config/share` → `/cowrie/cowrie-git/share/cowrie` (fs.pickle + txtcmds)
- `./cowrie_config/var` → `/cowrie/cowrie-git/var` (logs written here)

**Environment variables:**
- `COWRIE_HYBRID_LLM_API_KEY` — OpenAI API key
- `COWRIE_HYBRID_LLM_ENABLED=true` — Enables hybrid fallback
- `COWRIE_DB_*` — Database connection details (optional)

### Startup Sequence (honeypot_tools.py)

1. `start_dockers()` — Runs `docker-compose down` (clean slate) then `build` + `up -d`
2. `wait_for_cowrie()` — Polls container logs for "Ready to accept SSH connections" (up to 60s)
3. `wait_for_db()` — Checks Docker healthcheck status for database container (if present)

### The Cowrie Docker Image

**Dockerfile** (`Cowrie/cowrie-src/Dockerfile`):

1. **Builder stage** (debian:bookworm-slim)
   - Installs Python build tools, Rust compiler (needed for cryptography package)
   - Creates virtualenv, installs dependencies
   - Copies entire Cowrie source (including custom LLM modifications)

2. **Runtime stage** (gcr.io/distroless/python3-debian12)
   - Minimal image — no shell, no package manager
   - Copies virtualenv and Cowrie code from builder
   - Pre-compiles Python bytecode
   - Runs via Twisted daemon: `twistd -n cowrie`

---

## 7. Inside Cowrie — How Commands Are Handled

When an attacker types a command, it flows through several layers:

### Layer 1: SSH Protocol (`src/cowrie/ssh/`)

```
Attacker SSH client
    ↓
SSH Transport (transport.py) — Key exchange, encryption
    ↓
SSH Authentication (userauth.py) — Checks userdb.txt
    ↓
SSH Session (session.py) — Opens shell channel
    ↓
Shell Protocol (shell/protocol.py)
```

### Layer 2: Shell Protocol (`src/cowrie/shell/protocol.py`)

`HoneyPotInteractiveProtocol` handles the interactive shell:
- Displays the prompt (e.g., `root@wp-prod-01:~#`)
- Reads keystrokes, handles line editing (backspace, arrows, tab completion)
- On Enter: passes the command line to the shell parser

### Layer 3: Shell Parser (`src/cowrie/shell/honeypot.py`)

`HoneyPotShell.runCommand()` determines how to execute each command:

```
Command received: "cat /etc/passwd"
    ↓
1. Parse into tokens: ["cat", "/etc/passwd"]
    ↓
2. Resolve command path: getCommand("cat", ["/bin", "/usr/bin", ...])
    ↓
3. Lookup priority:
   a. Built-in command handler? (src/cowrie/commands/cat.py)  → YES → Execute handler
   b. Txtcmd file exists? (txtcmds/bin/cat)                  → Skip (cat has a handler)
   c. Hybrid LLM enabled?                                    → Fallback (if a+b fail)
   d. None of the above                                      → "command not found"
```

### Layer 4: Command Handlers (`src/cowrie/commands/`)

60 built-in handlers cover common Linux commands. Each handler is a Python class:

```python
# Example: commands/cat.py (simplified)
class Command_cat(HoneyPotCommand):
    def call(self):
        for arg in self.args:
            path = self.fs.resolve_path(arg, self.protocol.cwd)
            if self.fs.isfile(path):
                # Read from honeyfs (real file on disk)
                contents = self.fs.file_contents(path)
                self.write(contents)
            else:
                self.errorWrite(f"cat: {arg}: No such file or directory\n")
```

**How commands access files:**
- `self.fs` is the `HoneyPotFilesystem` instance (loaded from fs.pickle)
- `self.fs.file_contents(path)` reads from the honeyfs directory (real files on disk)
- `self.fs.exists(path)`, `self.fs.isdir(path)`, `self.fs.isfile(path)` check the pickle tree
- `self.fs.get_path(path)` lists directory contents

**Key built-in handlers:**

| Handler | What It Does |
|---------|-------------|
| `cat.py` | Reads file_contents from honeyfs |
| `ls.py` | Lists directory entries from fs.pickle |
| `cd.py` | Changes working directory |
| `wget.py` / `curl.py` | Simulates download (actually downloads to Cowrie's sandbox) |
| `ssh.py` | SSH client — supports real proxying in HoneyNet mode |
| `sudo.py` | Simulates privilege escalation |
| `apt.py` / `yum.py` | Simulates package installation |
| `docker.py` | Simulates Docker commands |
| `python.py` | Simulates Python interpreter |
| `adduser.py` | Simulates user creation |
| `chmod.py` / `chown.py` | Simulates permission changes |
| `ping.py` | Simulates network ping |
| `gcc.py` | Simulates compilation |

### Layer 5: Txtcmds — Static Output Files

For commands that need profile-specific output but don't need dynamic behavior, txtcmds provides pre-baked responses:

```
Attacker types: "uname -a"
    ↓
Cowrie checks: txtcmds/usr/bin/uname (exists!)
    ↓
Reads binary content of the file
    ↓
Returns: "Linux wp-prod-01 5.15.0-88-generic #98-Ubuntu SMP ..."
```

Txtcmds are checked **after** built-in handlers but **before** the LLM fallback.

---

## 8. The Hybrid LLM Fallback System

This is Project Violet's key innovation. When Cowrie encounters a command it doesn't have a handler or txtcmd for, it asks an LLM to generate a realistic response.

**File:** `src/cowrie/shell/llm_fallback.py` (~700 lines)

### When It Triggers

```
Attacker types: "systemctl status nginx"
    ↓
1. Built-in handler? → No (no systemctl.py command handler)
2. Txtcmd file? → No (not pre-generated)
3. Hybrid LLM enabled? → YES
    ↓
Forward to LLMFallbackHandler.handle_command("systemctl status nginx")
```

### How It Works

**Step 1: Check cache**
```python
# llm_cache.json persists across sessions
cache_key = hash(command + profile_hash)
if cache_key in cache:
    return cached_response  # No LLM call needed
```

The cache is keyed on `(command, profile_hash)` — if the profile changes, the cache invalidates.

**Step 2: Build context (pre-query)**

The `prequery.py` module extracts relevant context from the profile:
- If command mentions a file → include file_contents for that file
- If command mentions a service → include service config
- If command involves network → include network interfaces
- Session state (previous commands and their outputs) is included

**Step 3: Call the LLM**

```
System prompt: llm_prompt.txt (server description + rules)
User message: "The attacker ran: systemctl status nginx"
Context: [relevant file contents, service info, session history]
```

The LLM returns a realistic response:
```
● nginx.service - A high performance web server
     Loaded: loaded (/lib/systemd/system/nginx.service; enabled)
     Active: active (running) since Mon 2024-01-15 03:22:11 UTC
   Main PID: 1234 (nginx)
      Tasks: 5 (limit: 4915)
     Memory: 12.4M
```

**Step 4: Cache and return**

The response is saved to `llm_cache.json` so identical commands in future sessions don't need another LLM call.

### Session State Tracking

`SessionStateRegister` tracks up to 50 command/response pairs per session, pruned by impact score. This means the LLM knows what the attacker has already done and can maintain consistency (e.g., if the attacker created a file, the LLM "remembers" it exists).

### Database Proxy Integration

If the profile includes a database service and `COWRIE_DB_*` env vars are set, the LLM fallback can proxy real SQL queries to the actual database container:

```
Attacker types: "mysql -u root -p -e 'SHOW DATABASES;'"
    ↓
LLM fallback detects SQL context
    ↓
db_proxy.py connects to real MySQL container
    ↓
Executes query, returns real results
```

### Hot Reload (SIGUSR1)

The LLM fallback handler registers a SIGUSR1 signal handler. When Cowrie receives SIGUSR1, it reloads the profile from disk — enabling mid-experiment reconfiguration without restarting the container.

---

## 9. Sangria — The Attacker Simulation

Sangria is the LLM-driven attacker that probes the honeypot.

### Components

**`attacker_prompt.py`** — Builds the system prompt:
```
You are an expert penetration tester on a Kali Linux machine.
Your IP: 172.{RUNID}.0.2
Target: 172.{RUNID}.0.3 (or .0.10 in honeynet mode)

Available tools:
- terminal_input: Execute a command on Kali
- terminate: End the session

Objectives:
- Penetrate the target system
- Discover credentials and secrets
- Escalate privileges
- Establish persistence
- Attempt lateral movement
- Extract sensitive files
```

If `provide_honeypot_credentials=True`, the prompt also includes the SSH port and one valid username/password.

**`terminal_io.py`** — SSH connection to Kali:
```
Sangria LLM → "ssh root@172.10.0.3 -p 2222" → Kali container → SSH to Cowrie
```

The terminal I/O layer:
1. Spawns pexpect SSH session to Kali
2. Sends commands, waits for prompt patterns (`$` or `#`)
3. Captures output (truncated at 10,000 chars)
4. Handles multiline commands, heredocs, interactive prompts

**`sangria.py`** — Main attack loop:

```python
def run_single_attack(messages, max_session_length, ...):
    for turn in range(max_session_length):
        # 1. Ask LLM what to do next
        response = llm_client.chat(messages, tools=[terminal_input, terminate])

        # 2. Execute tool calls
        for tool_call in response.tool_calls:
            if tool_call.name == "terminal_input":
                output = terminal_io.send_command(tool_call.args["command"])
            elif tool_call.name == "terminate":
                return logs

        # 3. Read new Cowrie logs (what the honeypot recorded)
        hp_logs = honeypot_tools.get_new_hp_logs()

        # 4. Feed output + honeypot logs back to LLM
        messages.append(tool_response(output, hp_logs))

        # 5. LLM reasons about what happened, plans next move
        followup = llm_client.chat(messages)
        messages.append(followup)
```

### The Attack Flow (Typical Session)

```
Turn 1: Sangria → "ssh root@172.10.0.3 -p 2222" → Kali SSHs to Cowrie
Turn 2: Sangria → "whoami" → Cowrie returns "root" (txtcmd)
Turn 3: Sangria → "ls -la /root" → Cowrie returns directory listing (ls.py handler)
Turn 4: Sangria → "cat /root/.bash_history" → Cowrie returns history (cat.py + honeyfs)
Turn 5: Sangria → "cat /var/www/html/wp-config.php" → Finds DB credentials
Turn 6: Sangria → "mysql -u root -p" → LLM fallback generates MySQL prompt
Turn 7: Sangria → "cat /root/.ssh/id_rsa" → Finds SSH private key
Turn 8: Sangria → "ssh deploy@10.0.1.100" → Attempts lateral movement
...
```

---

## 10. Log Extraction and Feedback Loop

### What Cowrie Logs

Every command the attacker runs generates a JSON event in `cowrie.json`:

```json
{
  "eventid": "cowrie.command.input",
  "input": "cat /etc/passwd",
  "session": "abc123",
  "src_ip": "172.10.0.2",
  "username": "root",
  "timestamp": "2026-03-09T14:22:33.456789"
}
```

Other event types: `cowrie.session.connect`, `cowrie.session.closed`, `cowrie.command.failed`, `cowrie.login.success`, etc.

### How Logs Feed Back

**`log_extractor.py`** and **`honeypot_tools.get_new_hp_logs()`** track a byte offset into `cowrie.json`. Each call reads only new lines since the last read.

The extracted logs are injected into Sangria's context so the attacker LLM knows what the honeypot recorded — this creates a realistic feedback loop where the attacker can see results of their commands.

### Session Extraction

After each attack, `Sangria/extraction.py` parses the full conversation into a structured session:
- Commands executed
- MITRE ATT&CK tactics/techniques observed
- Credentials discovered
- Files accessed
- Session duration

These sessions feed into the reconfiguration system.

---

## 11. Reconfiguration Loop

Project Violet can **reconfigure the honeypot mid-experiment** based on attacker behavior.

### How It Works

```
Attack 1 → Session extracted → Reconfigurator.update(session)
Attack 2 → Session extracted → Reconfigurator.update(session)
...
Attack N → should_reconfigure() returns True!
    ↓
1. Generate new profile (LLM-based, novelty-checked)
2. Enrich with lures
3. Stop Cowrie container
4. Deploy new profile artifacts
5. Restart Cowrie container
6. Continue with attacks against new configuration
```

### Reconfiguration Criteria

| Method | How It Decides |
|--------|---------------|
| `NO_RECONFIG` | Never reconfigure |
| `BASIC` | Fixed interval (every N sessions) |
| `ENTROPY` | When command/technique entropy stabilizes (attacker behavior plateaus) |
| `T_TEST` | Statistical test on tactic sequences (detects significant behavior changes) |

---

## 12. HoneyNet Mode — Multi-Hop Chains

When `config.honeynet_enabled = True`, the system deploys multiple Cowrie instances connected in a chain.

### Network Topology

```
Kali (172.10.0.2)
  │
  │ SSH to port 2210:2222
  ▼
┌──────────────────┐     net_hop1          ┌──────────────────┐
│  Pot1 (Entry)    │  ←──────────────────→ │  Pot2            │
│  172.10.0.10     │   172.10.1.10         │  172.10.1.11     │
│  wordpress_server│   (pot1's outbound)   │  database_server │
└──────────────────┘                       └───────┬──────────┘
                                                   │ net_hop2
                                           172.10.2.11 (pot2's outbound)
                                                   │
                                           ┌───────┴──────────┐
                                           │  Pot3            │
                                           │  172.10.2.12     │
                                           │  cicd_runner     │
                                           └──────────────────┘
```

**Key properties:**
- Kali can only reach Pot1 (net_entry network)
- Each pot sits on two networks (inbound + outbound), except the last pot
- Pots cannot reach "upward" — Pot2 cannot initiate connections to Pot1

### Breadcrumb Injection

`credential_chain.py` injects real next-hop credentials into each profile:

1. **`/etc/hosts`** — Adds `172.10.1.11  db-prod-01`
2. **`.bash_history`** — Adds `ssh root@172.10.1.11 -p 2222`
3. **`~/.ssh/config`** — Adds Host block with HostName, User, Port
4. **`/opt/.env`** — Adds `INTERNAL_HOST=172.10.1.11`, `INTERNAL_SSH_PASS=...`
5. **`lateral_movement_targets`** — Adds next-hop IP to lure metadata

### Real SSH Proxying

When the attacker (on Pot1) runs `ssh root@172.10.1.11`, Cowrie's custom `ssh.py` handler:

1. Detects `HONEYNET_MODE=true` environment variable
2. Creates `SSHProxySession` (uses paramiko for real SSH)
3. Opens a real SSH connection to Pot2's container
4. Relays I/O bidirectionally: attacker keystrokes → Pot2, Pot2 output → attacker

The attacker gets a **real interactive shell** on Pot2 — not a simulation.

### Session Correlation

After the experiment, `Purple/session_correlator.py` correlates sessions across hops:

```
Pot1 log: session from 172.10.0.2 (Kali) → commands executed
Pot2 log: session from 172.10.1.10 (Pot1's IP) → commands executed
Pot3 log: session from 172.10.2.11 (Pot2's IP) → commands executed
```

By matching source IPs across hops, it reconstructs the attacker's full journey and calculates:
- Total dwell time
- Per-hop dwell time and command count
- Pivot success rate
- Files accessed per hop
- Maximum hop depth reached

---

## 13. End-to-End Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXPERIMENT START                             │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  1. Load JSON Profile   │  Reconfigurator/profiles/wordpress_server.json
│     (config.py)         │
└─────────────┬───────────┘
              │
              ▼
┌─────────────────────────┐
│  2. Enrich Lures        │  lure_agent.py → LLM fills credential gaps
│     (lure_agent.py)     │  Adds .env files, SSH keys, breadcrumbs
└─────────────┬───────────┘
              │
              ▼
┌─────────────────────────┐  ┌──────────────────────────────────────┐
│  3. Convert Profile     │  │ Outputs:                             │
│     (profile_converter) │→ │  - fs.pickle (virtual filesystem)    │
│                         │  │  - honeyfs/ (file contents on disk)  │
│                         │  │  - txtcmds/ (static command outputs) │
│                         │  │  - userdb.txt (SSH credentials)      │
│                         │  │  - llm_prompt.txt (LLM context)      │
│                         │  │  - profile.json (full profile)       │
│                         │  │  - cowrie.cfg (configuration)        │
└─────────────┬───────────┘  └──────────────────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  4. Start Docker        │  docker-compose up -d
│     (honeypot_tools)    │  Wait for Cowrie "Ready to accept SSH"
└─────────────┬───────────┘
              │
              ▼
┌─────────────────────────┐
│  5. Sangria Attack Loop │  For each session (config.num_of_sessions):
│     (sangria.py)        │
└─────────────┬───────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────┐
│  ATTACK TURN:                                                    │
│                                                                  │
│  Sangria LLM                                                     │
│    │ "Run: ssh root@172.10.0.3 -p 2222"                        │
│    ▼                                                             │
│  Kali Container (terminal_io.py)                                 │
│    │ Executes SSH command                                        │
│    ▼                                                             │
│  Cowrie Container                                                │
│    │                                                             │
│    ├─ SSH Protocol → Authentication (userdb.txt)                 │
│    ├─ Shell Protocol → Parse command                             │
│    ├─ Command Lookup:                                            │
│    │   ├─ Built-in handler? (commands/*.py)  ──→ Execute         │
│    │   ├─ Txtcmd file? (txtcmds/*)           ──→ Return content  │
│    │   └─ LLM Fallback? (llm_fallback.py)    ──→ Query LLM      │
│    │       ├─ Check cache (llm_cache.json)                       │
│    │       ├─ Build context (prequery.py)                        │
│    │       ├─ Call OpenAI API                                    │
│    │       └─ Cache + return response                            │
│    │                                                             │
│    ▼                                                             │
│  Response returned to attacker via SSH                           │
│    │                                                             │
│    ▼                                                             │
│  Cowrie writes event to cowrie.json                              │
│    │                                                             │
│    ▼                                                             │
│  log_extractor reads new events                                  │
│    │                                                             │
│    ▼                                                             │
│  Sangria receives output + honeypot logs → Plans next command    │
│                                                                  │
│  [Repeat for max_session_length turns]                           │
└──────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  6. Extract Session     │  Commands, tactics, techniques, credentials
│     (extraction.py)     │
└─────────────┬───────────┘
              │
              ▼
┌─────────────────────────┐
│  7. Should Reconfigure? │  Entropy / T-test / Basic interval check
│     (reconfigurator)    │
└──────┬──────────────┬───┘
       │ No           │ Yes
       ▼              ▼
   [Next attack]   ┌──────────────────────────┐
                   │  8. Generate New Profile  │  LLM creates new server theme
                   │  9. Re-deploy Cowrie      │  Stop → Convert → Start
                   │  10. Continue attacks     │
                   └──────────────────────────┘
              │
              ▼
┌─────────────────────────┐
│  11. Experiment Done    │  All sessions complete
│      Analysis (Purple)  │  Session correlation, MITRE mapping, metrics
└─────────────────────────┘
```

---

## Command Resolution Priority (Summary)

When an attacker types any command, Cowrie resolves it in this order:

```
1. Built-in Python handler (commands/*.py)     → Fastest, most realistic
   Examples: cat, ls, cd, wget, curl, ssh, sudo, docker, apt, python

2. Txtcmd static file (share/txtcmds/*)        → Fast, profile-specific
   Examples: uname, ps aux, ifconfig, netstat, df, free, whoami, id

3. Hybrid LLM fallback (llm_fallback.py)       → Slower, handles ANYTHING
   Examples: systemctl status, docker ps, htop, vim, mysql, custom tools
   - Checks disk cache first (llm_cache.json)
   - Falls back to LLM API call if not cached
   - Caches response for future use

4. "Command not found"                          → Last resort
   Only if hybrid_llm is disabled
```

This layered approach means common commands are fast and consistent, while the LLM handles the long tail of unexpected commands — making the honeypot convincing regardless of what the attacker tries.
