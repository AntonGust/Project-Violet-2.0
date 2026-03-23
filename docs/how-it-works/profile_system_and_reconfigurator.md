# Profile System and Reconfigurator

## Overview

The Profile System and Reconfigurator form the intelligent backbone of dynamic honeypot configuration. The system uses LLM-driven profile generation to create realistic server personas, enriches them with interconnected lures, validates them against schema and engagement requirements, and converts them into Cowrie honeypot artifacts. The reconfiguration pipeline enables adaptive honeypots that evolve based on attacker behavior.

## Profile JSON Structure

A profile defines a complete server persona with 8 required top-level fields:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Unique identifier (auto-assigned) |
| `system` | Object | OS identity: os, hostname, kernel_version, arch, timezone |
| `users` | Array | User accounts with UID/GID, shell, password_hash, groups, sudo_rules |
| `directory_tree` | Object | Filesystem structure: path → array of entries (name, type, permissions, owner, group, size) |
| `file_contents` | Object | File path → text content (for honeyfs) |
| `services` | Array | Running processes: name, pid, user, command, ports |
| `ssh_config` | Object | SSH settings and accepted_passwords (username → array of passwords) |
| `description` | String | Human-readable summary |

Plus optional: `network` (interfaces), `installed_packages` (name, version), `crontabs` (user → crontab), `disk_layout` (filesystem, size, used, mount).

## Profile Inventory (16 Profiles)

**Original 3:** wordpress_server, database_server, cicd_runner

**New 10 (generated 2026-03-06):** mail_server, vpn_gateway, monitoring_stack, file_server, dns_server, git_server, docker_swarm, backup_server, dev_workstation, iot_gateway

Each profile is 18-31KB of JSON defining a complete server environment.

## Generation Pipeline (`new_config_pipeline.py`)

### Step 1: Sample Previous Profiles
Scans `hp_config_*/honeypot_config.json` and `sessions.json` from previous experiment runs. Returns up to 5 random profiles with their session data (observed tactics/techniques). Used to inform the LLM for novelty.

### Step 2: Build LLM Prompt
Includes the full JSON schema, a **Lure Engagement Strategy** section with 6 required lure categories and minimums, instruction to create interconnected lures, and summaries of previous profiles with a directive to be different.

### Step 3: Query LLM
Uses the configured reconfig model (default: Llama 3.3 70B via TogetherAI) at temperature 0.7.

### Step 4: Parse and Finalize
- Extract JSON from LLM output
- Assign UUID and ISO 8601 timestamp
- Ensure root user and at least one non-root SSH user
- Strip unknown top-level keys
- Remove null values

### Step 5: Triple Validation (3 attempts)

1. **Schema validation** — jsonschema against `filesystem_profile_schema.json`
2. **Lure coverage validation** — checks 6 categories against minimums
3. **Novelty check** — profile distance must be >= 0.4 from all previous profiles

## Lure Requirements (6 Categories)

| Category | Min | Detection Method |
|----------|-----|-----------------|
| `breadcrumb_credentials` | 4 | Files with content matching `password\|passwd\|secret\|_key\|token` |
| `lateral_movement_targets` | 2 | Non-localhost entries in /etc/hosts + SSH config files + internal IPs in scripts |
| `privilege_escalation_paths` | 1 | Non-root users with sudo_rules or docker group + writable crontabs |
| `active_system_indicators` | 3 | Files under /var/log/, /var/mail/, /tmp, or named .bash_history |
| `explorable_applications` | 1 | Paths matching `wp-config\|docker-compose\|\.git\|redis\.conf\|nginx\.conf\|...` |
| `rabbit_holes` | 2 | file_contents entries > 500 characters |

## Lure Enrichment (`lure_agent.py`)

After generation, optional LLM-driven enrichment extends lures with 4 additional categories:

| Category | Description |
|----------|-------------|
| `cloud_credentials` | AWS keys, GCP service accounts, Azure connection strings |
| `container_escape_paths` | docker.sock, privileged containers, K8s tokens |
| `cicd_tokens` | GitLab, GitHub, Jenkins tokens |
| `supply_chain_artifacts` | npm tokens, PyPI credentials, private registries |

The enrichment agent also generates **lure chains** — multi-step attack sequences:

```json
{
  "chain_id": "chain-001",
  "name": "Container Escape via Docker Socket to Jenkins",
  "steps": [
    {"file": "/home/deploy/.docker/config.json", "leads_to": "/var/run/docker.sock"},
    {"file": "/var/run/docker.sock", "leads_to": "/home/deploy/.jenkins_api_token"},
    {"file": "/home/deploy/.jenkins_api_token", "leads_to": null}
  ]
}
```

## Profile Distance (`profile_distance.py`)

Novelty detection uses weighted Jaccard distance across 5 dimensions:

| Dimension | Type | Weight |
|-----------|------|--------|
| OS Family | Binary (0.0 or 1.0) | 1 |
| Service Set | Jaccard distance | 1 |
| Lure File Paths | Jaccard distance | 1 |
| Non-Root Users | Jaccard distance | 1 |
| Listening Ports | Jaccard distance | 1 |

**Final distance** = mean of all 5 scores. Threshold: 0.4 (configurable). If any previous profile has distance < threshold, the new profile is rejected as not novel enough.

## Reconfiguration Triggers (`config.py`)

| Method | Trigger | Config |
|--------|---------|--------|
| `NO_RECONFIG` | Never | — |
| `BASIC` | Every N sessions | `ba_interval` |
| `ENTROPY` | When Shannon entropy of tactic/technique distribution drops below threshold | `en_variable`, `en_window_size`, `en_tolerance` |
| `T_TEST` | When Welch's t-test detects statistically significant shift in tactic distribution | `tt_variable`, `tt_tolerance`, `tt_confidence` |

**ENTROPY logic:** Low entropy = attacker stuck in repetitive behavior = time to change the environment.

**T_TEST logic:** Compare recent session window vs. older window. If tactic distributions are statistically similar (p-value < tolerance), attacker has converged.

## Database Seed Generation (`db_seed_generator.py`)

When a profile includes database services, the system generates real database containers with seed data.

### Engine Detection
Checks services and packages for MySQL/MariaDB or PostgreSQL indicators.

### Credential Extraction
- **MySQL:** parses wp-config.php (`define('DB_USER', ...)`), .env files (`DB_USER=`), shell scripts (`MYSQL_PWD=`)
- **PostgreSQL:** parses .pgpass, pgbouncer userlist.txt, shell scripts (`PGPASSWORD=`)

### SQL Generation
- **MySQL:** WordPress schema (wp_users, wp_posts, wp_comments, wp_options, etc.) with ~500 rows of deterministic seed data
- **PostgreSQL:** Business application schema (users, transactions, audit_log, sessions, api_keys, config) with ~415 rows

## Profile Converter (`profile_converter.py`)

Transforms a profile JSON into 7 Cowrie artifacts:

### 1. fs.pickle (Virtual Filesystem Tree)
Binary-serialized tree where each node is a 10-element list: `[name, type, uid, gid, size, mode, ctime, contents, target, realfile]`.

Includes:
- 100+ standard Linux directories with install-time timestamps (~90 days ago)
- Profile directory_tree entries with recent timestamps (1-7 days ago)
- Auto-generated system files (/etc/passwd, /etc/shadow, /etc/group, /etc/hostname, /etc/os-release, /etc/hosts, /etc/resolv.conf, /etc/fstab, etc.)
- SUID binaries (/usr/bin/passwd, /usr/bin/sudo, /usr/bin/ping, etc.) — without these, `find / -perm -4000` would immediately reveal a fake filesystem
- Systemd service files for each profile service

### 2. honeyfs/ (File Contents)
Real files on disk mirroring the profile's `file_contents`. Used by `cat`, `head`, `tail`, `grep`. Includes auto-generated /etc/passwd, /etc/shadow, /etc/group with proper formatting.

### 3. txtcmds/ (Static Command Outputs)
Static text files for `uname`, `hostname`, `ps`, `ifconfig`, `netstat`, `df`, `free`, `last`, `uptime`, `whoami`, `id`, `arch`. All derived from the profile's system, services, and network data.

### 4. userdb.txt (SSH Credentials)
Cowrie's authentication database. Format: `username:uid:password` per line. Derived from `ssh_config.accepted_passwords`.

### 5. LLM System Prompt
Fallback prompt for the hybrid LLM handler. Includes system context (OS, services, ports, users) and rules for consistent simulation.

### 6. cmdoutput.json
Structured JSON for Cowrie's native `ps` handler. Includes realistic VSZ/RSS values per service.

### 7. profile.json
Copy of the full profile for runtime access by the LLM fallback handler's prequery system.

## Full Deployment Flow

```
1. Load profile JSON
2. Enrich AWS context (if applicable)
3. Generate fs.pickle → cowrie_config/share/fs.pickle
4. Generate honeyfs/ → cowrie_config/honeyfs/
5. Generate txtcmds/ → cowrie_config/share/txtcmds/
6. Generate userdb.txt → cowrie_config/etc/userdb.txt
7. Generate LLM prompt → cowrie_config/etc/llm_prompt.txt
8. Generate profile.json → cowrie_config/etc/profile.json
9. Generate cmdoutput.json → cowrie_config/share/cowrie/cmdoutput.json
10. [If CHeaT enabled] Apply defenses to profile and txtcmds
11. [If HoneyNet] Inject breadcrumbs for next hop
```
