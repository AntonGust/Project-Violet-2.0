# Changelog

## 2026-03-25 (c) — Hardening: Native MySQL Results, nmap Handler, MySQL Service Check

Post-run analysis of `logs/Harden_wordpress_server_2026-03-25T13_10_41` revealed the LLM fallback returning empty responses for MySQL queries, `nmap` missing on hop 3, and MySQL accepting connections on hosts without a MySQL service.

### Native MySQL Result Generation (`Cowrie/cowrie-src/src/cowrie/commands/mysql.py`)

- **Problem**: `SHOW DATABASES`, `SELECT * FROM wp_users`, and inline `-e` queries all returned empty output on hop 1. The LLM fallback generated empty or connection-error responses, causing the attacker to note "The output seems to not be showing properly."
- **Fix**: Common SQL queries are now answered natively from profile data before reaching the LLM. `SHOW DATABASES` extracts database names from `wp-config.php`, `.env`, and SQL dumps. `SHOW TABLES` and `SELECT * FROM <table>` parse `CREATE TABLE` / `INSERT INTO` statements from profile SQL dumps. Results are formatted as authentic MySQL ASCII tables. Priority chain: native profile data → DB proxy direct execution → LLM fallback.

### nmap Command Handler (`Cowrie/cowrie-src/src/cowrie/commands/nmap.py` — new)

- **Problem**: `nmap -sn` on hop 3 (cicd_runner) returned `command not found` four times, forcing the attacker into blind SSH attempts.
- **Fix**: New `nmap.py` handler delegates to LLM fallback with network context (registered in `prequery.py` `_COMMAND_FAMILIES`). Falls back to minimal static "0 hosts up" output when LLM is unavailable. Supports `--help` and `--version`.

### MySQL Service Validation at Login (`Cowrie/cowrie-src/src/cowrie/commands/mysql.py`)

- **Problem**: On hop 3 (cicd_runner, no MySQL service), `mysql` entered an interactive shell and returned `"Empty set (0.00 sec)"` for queries — the handler suppressed "Can't connect" errors from the LLM into "Empty set", which is semantically wrong.
- **Fix**: `_do_login()` now checks the profile for a MySQL/MariaDB service. If absent, returns `ERROR 2002 (HY000): Can't connect` and exits immediately. Removed the `"Can't connect" → "Empty set"` suppression in `_write_sql_result()`.

## 2026-03-25 (b) — Fix: SSH Loopback on Unreachable Hosts + Exploration Tracking

Two fixes for the fake SSH loopback issue documented in `docs/known-problems/cowrie-fake-ssh-loopback.md`.

### SSH Loopback Eliminated (`Cowrie/cowrie-src/src/cowrie/commands/ssh.py`)

- **Problem**: When the attacker SSHed to an internal IP that wasn't a real container (e.g., `10.0.1.20` from hop 1), Cowrie's proxy failed, then `_simulated_login()` faked a new shell on the same hop. The attacker saw `root@localhost:~#`, believed it had pivoted, and re-explored the same files. Each fake SSH also created a new Cowrie session ID, inflating session counts.
- **Fix**: Removed `_simulated_login()` entirely. Both `_proxy_connect_result(CONNECT_UNREACHABLE)` and `_proxy_connect_error()` now return `"Connection timed out"` and exit. The `/etc/hosts` fast-fail in `start()` is unchanged — unknown IPs still get instant "Connection refused" without a password prompt.

### Per-Host Exploration Tracking (`Sangria/attack_state.py`)

- **Problem**: `history_window=40` trimmed old messages, causing the LLM to forget which files it had already read on the current host and repeat identical recon commands.
- **Fix**: `HostEntry` gains `files_explored` (count of files read) and `fully_explored` fields. `to_prompt_string()` now shows per-host file counts (e.g., `"172.10.0.3 (wp-prod-01) — root access — visited — 7 files read"`). New `_update_exploration_count()` method called after every file read keeps the count current in the state register, which survives history windowing.

## 2026-03-25 — OpenRouter Provider Support

Added OpenRouter as an LLM provider, giving access to 200+ models (Claude, Gemini, Llama, DeepSeek, Qwen, etc.) through a single API key.

### Changes

- **`Utils/llm_client.py`**: Added `"openrouter"` to `_PROVIDER_URLS` (`https://openrouter.ai/api/v1`) and `_PROVIDER_ENV_KEYS` (`OPENROUTER_API_KEY`).
- **`Sangria/model.py`**: Added `LLMModel` entries: `OR_CLAUDE_4_SONNET`, `OR_GEMINI_2_5_PRO`, `OR_DEEPSEEK_R1`, `OR_QWEN_3_235B`.
- **`Sangria/sangria.py`**: Added `MODEL_PRICING` entries for the 4 OpenRouter models.
- **`config.py`**: Updated provider option comments to include `"openrouter"`.

### Usage

Set `OPENROUTER_API_KEY` in `.env`, then `llm_provider = "openrouter"` in `config.py`. Any OpenRouter model ID can also be passed as a plain string.

## 2026-03-24 (b) — Hardening: HONEYPOT_LURE Removal, SSH Fallback, Hostname Fix

Post-run analysis of `logs/Harden_wordpress_server_2026-03-24T20_42_11` revealed the attacker detected the honeypot at iteration 128 due to a `HONEYPOT_LURE` prefix in credential values. Three fixes applied.

### HONEYPOT_LURE Credential Placeholders (6 profiles)

- **Problem**: Profile files contained credentials prefixed with the literal text `HONEYPOT_LURE_` (e.g., `HONEYPOT_LURE_gitlab_pat_abcdef1234567890`). The attacker read `/home/dba/.gitlab-ci.yml` on hop 2 and immediately identified this as a honeypot indicator.
- **Fix**: All 6 profiles (`database_server`, `cicd_runner`, `monitoring_stack`, `backup_server`, `docker_swarm`, `dev_workstation`) now use bland `REDACTED_*` placeholders in git. `scripts/.lure_secrets` updated with new placeholder-to-realistic mappings. `scripts/gcp_lure.py` placeholder also renamed. The `restore_lure_secrets.sh` workflow verified end-to-end.

### SSH Simulated Fallback for Unreachable Hosts (`Cowrie/cowrie-src/src/cowrie/commands/ssh_proxy.py`, `ssh.py`)

- **Problem**: When the attacker SSHed to internal IPs from hop 2 (e.g., 10.0.3.15 db-standby), the proxy attempted a real TCP connection, failed, and returned "Connection refused" instantly. The existing simulated-shell fallback in `_proxy_connect_error()` never triggered because `ssh_proxy.connect()` returned `False` (handled by `_proxy_connect_result` which just called `exit()`).
- **Fix**: `ssh_proxy.connect()` now returns a 3-value result: `CONNECT_OK`, `CONNECT_AUTH_FAILED`, or `CONNECT_UNREACHABLE`. Exception handling differentiates `socket.timeout`, `ConnectionRefusedError`, and `paramiko.AuthenticationException`. `_proxy_connect_result()` routes `CONNECT_UNREACHABLE` to `_proxy_connect_error()`, which checks `/etc/hosts` and provides a simulated shell for known hosts instead of "Connection refused".

### Hostname Tracking Fallback Removed (`Sangria/attack_state.py`)

- **Problem**: The fallback in `_update_current_host()` (lines 454-459) iterated through all visited hosts and assigned the current hostname to the first match when `_last_ssh_target_ip` was empty. Since the field is cleared after each SSH command, every subsequent non-SSH command triggered the fallback, overwriting hop 1's hostname ("wp-prod-01") with hop 2's ("db-primary").
- **Fix**: Removed the fallback entirely. Hostnames are only assigned via the explicit `_last_ssh_target_ip` path from SSH commands. The `current_host` prompt string still tracks the active session correctly for display and logging.

## 2026-03-24 — Honeynet Hardening: Star Topology, Credential Scatter, CHeaT Expansion

Diagnostic analysis of `logs/Testing_2026-03-24T17_15_29` revealed 6 issues. All fixed.

### Star Network Topology (`Blue_Lagoon/compose_generator.py`, `Blue_Lagoon/credential_chain.py`)

- **Problem**: Chain-linked networks (Kali→hop1→hop2→hop3) meant the attacker could only reach each hop through the previous one. A command timeout on hop3 collapsed the entire SSH chain, ejecting the attacker to Kali with no way to reconnect without re-traversing all hops.
- **Fix**: All honeypot hops now share a `net_attack` network (172.{run_id}.0.0/24) directly reachable from Kali. Each hop also keeps a private `net_internal_N` network for database containers and profile realism. `HopInfo` gains `attack_ip`, `internal_ip`, and `internal_subnet` fields.
- **Session correlator updated**: `Purple/session_correlator.py` now matches sessions by attack_ip instead of chain-linked IPs, and tracks all attacker-controlled IPs (Kali + any compromised hop).

### Credential Chain Realism (`Blue_Lagoon/credential_chain.py`)

- **Problem**: Each hop had `/opt/.env` with plaintext SSH credentials for the next hop. The attacker found them in 2 commands (`find / -name "*.env"` → `cat /opt/.env`), pivoting with zero effort.
- **Fix**: Credentials are now scattered across multiple files:
  - **Username + host**: in `.bash_history` and `~/.ssh/config` (no password)
  - **Password**: placed randomly in one of 4 realistic locations (backup scripts, root mail, notes files, deploy configs)
  - **2 decoy credential sets** per hop in `/opt/.env.bak` and `/var/backups/credentials.old` — look real but use wrong usernames/passwords, increasing dwell time and CHeaT detection surface.
- The `/opt/.env` all-in-one breadcrumb pattern is removed entirely.

### CHeaT Defenses on All Hops (`main.py`, `config.py`)

- **Problem**: CHeaT defenses (unicode honeytokens, canary URLs, prompt traps, tool traps) were only applied to hop 0. The attacker reached hops 2-3 with zero detection coverage. Canary URLs, prompt traps, and tool traps were disabled by default.
- **Fix**: CHeaT defenses are now applied to every hop in the honeynet loop. Defense metadata is stored per-hop (`{"hop_1": {...}, "hop_2": {...}}`) and flattened for the detector via `_flatten_per_hop_defenses()`. All CHeaT modules enabled by default: `cheat_canary_urls=True`, `cheat_prompt_traps=True`, `cheat_tool_traps=True`.

### Hostname Tracking Fix (`Sangria/attack_state.py`)

- **Problem**: `_update_current_host()` assigned hostnames to the wrong IPs. After SSH-ing to `172.10.1.11` (db-primary), the hostname was assigned to the first unmatched visited host instead of the SSH target, producing incorrect mappings like `172.10.1.11 → wp-prod-01`.
- **Fix**: New `_last_ssh_target_ip` field tracks the IP from the most recent SSH command. `_update_current_host()` assigns the discovered hostname to that specific IP, then clears the field. Falls back to the old heuristic only when no SSH target is tracked.

### OS-Aware MOTD Templates (`Reconfigurator/profile_converter.py`)

- **Problem**: All hops used a hardcoded Ubuntu-style MOTD regardless of profile OS. CentOS hops showed Ubuntu help URLs. All hops had identical system stats (0.08 load, 142 processes, 42% memory).
- **Fix**: New `_generate_motd()` function with `_detect_os_family()` selects appropriate help URLs per OS (Ubuntu, CentOS, Debian, RHEL). System stats (load, processes, disk, memory, swap) and timestamps are randomized per hop.

### Timeout Configuration (`main.py`)

- Interactive timeout increased from 600s to 900s, idle timeout from 300s to 600s. Combined with star topology, timeouts are no longer session-fatal — the attacker can SSH directly back to any discovered hop.

## 2026-03-23 — CHeaT Honeytoken Fix, Secret Sanitization, README

### CHeaT Unicode Honeytokens Fix (`Reconfigurator/cheat/unicode_tokens.py`)

- **Root cause**: `inject_unicode_honeytokens()` modified `ssh_config.accepted_passwords` — the actual credentials Cowrie uses for authentication. The injected zero-width Unicode characters made the passwords impossible for the LLM attacker to reproduce, so SSH login always failed.
- **Fix 1**: Honeytokens are no longer injected into `accepted_passwords`. They are only applied to `file_contents` (what the attacker reads on the honeypot filesystem), which is where copy-paste detection matters.
- **Fix 2**: Honeytokens are now applied to a random 30–50% subset of credential-bearing files instead of every file. This makes detection less predictable and more realistic.
- **Symptom fixed**: Attacker spent all 200 iterations brute-forcing passwords that could never work because the real Cowrie credentials contained invisible Unicode.

### Secret Sanitization for GitHub Push Protection (`scripts/`)

- **Problem**: GitHub push protection blocked pushes due to realistic lure secrets (Grafana tokens, Stripe keys, Slack webhooks, GCP service account) committed in profile JSON and the restore script itself.
- **`restore_lure_secrets.sh` rewritten**: Secret mappings moved from the script to `scripts/.lure_secrets` (gitignored). The committed script contains no real secret values.
- **`gcp_lure.py` added**: Python helper for the GCP service account JSON blob in `dev_workstation.json` — sed cannot handle multi-line JSON replacements reliably.
- **Workflow**: `--sanitize` before commit, `--restore` after checkout (also available from Settings menu in `main_menu.py`).
- **`.gitignore` updated**: Added `.env`, `scripts/.lure_secrets`, `cowrie_config*/var/`, `__pycache__/`, `logs/`.

### README Updated for Project Violet 2.0

- Full rewrite covering architecture, multi-hop honeynet, CHeaT defenses, all LLM providers, reconfiguration methods, output structure, and lure secret management.

## 2026-03-18 — Hardening Fixes: DB Proxy IP, Attacker Loop Prevention, Profile Authenticity

### Compose Generator DB IP Fix (`Blue_Lagoon/compose_generator.py`)

- **Root cause**: `_inject_db_env()` read `ip_suffix` from `db_config.json` with a default of `"0.4"`, producing `COWRIE_DB_HOST=172.10.0.4`. But `_build_db_service()` assigns DB container IPs as `172.{run_id}.{hop_index}.{20+hop_num}` — e.g. `172.10.0.21` for hop1 MySQL. The mismatch meant Cowrie's DBProxy always connected to the wrong IP, causing `ERROR 2003` on every SQL query.
- **Fix**: `_inject_db_env()` now computes the DB host IP using the same formula as `_build_db_service()`, taking `hop_index` as a new parameter. Manual edits to `docker-compose.honeynet.yml` are no longer needed — the generator produces correct IPs.
- **Symptom fixed**: `mysql -u wp_admin -p` showed a welcome banner (from the command handler) but `SHOW DATABASES;` returned `ERROR 2003 (HY000): Can't connect to MySQL server on 'localhost' (111)`.

### Attacker SSH Loop Prevention (`Sangria/attack_state.py`)

- **Root cause**: Commands were deduplicated by `(current_host, command)` tuples, but `current_host` was never reset when the attacker exited SSH. The Kali prompt (`┌──(root㉿hostname)-[~]`) uses `㉿` instead of `@`, so `_PROMPT_RE` didn't match it. After exiting SSH, `current_host` stayed as e.g. `"deploy@wp-prod-01"`, making subsequent SSH commands appear as new `(host, cmd)` pairs — bypassing dedup.
- **Fix 1**: `_update_current_host()` now detects "Connection to X closed" in response output and parses the Kali `㉿` prompt format to correctly reset `current_host` to the Kali machine.
- **Fix 2**: New `_visited_ssh_targets` set tracks all SSH `user@ip:port` targets globally. Injected into the system prompt as "SSH TARGETS ALREADY VISITED (do NOT reconnect to these)".
- **Symptom fixed**: Attacker SSH'd to the same target 9+ times, repeating identical `find`/`cat`/`mysql` sequences each time, wasting ~300 of 370 messages.

### WordPress Profile Authenticity Fixes (`Reconfigurator/profiles/wordpress_server.json`)

- **Fake shadow hashes replaced**: `$6$rounds=656000$abc$fakehashroot` → realistic 86-char SHA-512 hashes with proper salt lengths. The literal string "fakehash" in the hash field is a honeypot detection signal.
- **`/etc/apache2/apache2.conf` content added**: File was declared in `directory_tree` but missing from `file_contents`, returning empty output when `cat`'d. In v7, this directly caused the attacker to detect the honeypot and terminate. Now returns a standard Ubuntu Apache2 config.
- **`/etc/apache2/envvars` content added**: Same gap — now returns standard Apache environment variables.

## 2026-03-18 — Profile Content Gap Filling, `/sc:fill-profile` Skill, Token Cost Fix

### `/sc:fill-profile` Skill (`~/.claude/commands/sc/fill-profile.md`)

- **New Claude Code skill** that audits honeypot profiles for content gaps between `directory_tree` declarations and `file_contents` entries, then generates authentic file contents for each gap.
- **Workflow**: Load profile → cross-reference declared files vs content → classify gaps by priority (P1 must-fill, P2 should-fill, P3 nice-to-have, Skip) → generate content → apply and validate JSON.
- **Honeynet anti-fingerprinting** (rule #6): When a profile is used in a multi-hop honeynet, generated content must be unique to that profile's role. `.bash_history`, `.bashrc` aliases, config files, and logs must reflect the profile's services — not be copy-pasted across hops. Cross-checks `config.py` → `chain_profiles` to prevent duplication.

### WordPress Server Profile Content Fill (`Reconfigurator/profiles/wordpress_server.json`)

- **14 files added** to close all explorable content gaps:
  - **P1**: `/root/.ssh/known_hosts` (corroborates network map), `/tmp/wp_migrate_2026.sql` (WP user table dump with phashed passwords)
  - **P2**: `.bashrc` (root + deploy with WP-specific aliases), `index.php` (stock WP front controller), `my.cnf`, `000-default.conf`, `authorized_keys`, `id_rsa.pub`
  - **P3**: `certbot` cron, `backup` cron, `ports.conf`, `wp-prod-01.conf` (letsencrypt renewal)
- Profile is now **31/34** files filled (remaining 3 are large boilerplate: `apache2.conf`, `envvars`, `php.ini`).

### Database Server Profile Content Fill (`Reconfigurator/profiles/database_server.json`)

- **12 files added** — all CentOS/PostgreSQL-specific, no overlap with wordpress profile:
  - **P1**: `known_hosts` (db cluster hosts), `id_rsa` (DBA SSH key), `authorized_keys` (monitoring + app-server access), `replicate_to_standby.sh` (WAL replication script), `pgbouncer.ini` (connection pooler config with pool settings)
  - **P2**: `.bashrc` (root/dba/backupuser — each with role-appropriate aliases like `pgstat`, `pgrepl`, `pgsize`), `pg_ident.conf`, `server.crt`, `server.key`
  - **P3**: `postgresql.conf` (full production config with replication, SSL, logging, autovacuum)
- Profile is now **34/38** files filled (remaining 4 are binary `.sql.gz` backups and Unix sockets).

### Honeypot Token Cost Fix (`main.py`)

- **Bug fix**: Honeypot cost calculation was double-counting cached tokens — charging them at the full input rate AND the cached rate. Fixed by subtracting `cached_tokens` from `prompt_tokens` before applying the input rate, matching how the Sangria (attacker) side already calculates it.
- Dormant with Together AI (cached_tokens always 0), but would have produced inflated costs when switching to OpenAI models.

## 2026-03-18 — Honeypot LLM API Key Fix, Anti-Loop State Register, DB on Hop1

### Honeypot LLM API Key Resolution (`main.py`, `Blue_Lagoon/honeypot_tools.py`)

- **Root cause**: Cowrie's LLM fallback inside Docker was receiving the wrong API key. The compose env var `COWRIE_HYBRID_LLM_API_KEY` was set from `OPENAI_API_KEY`, but when the honeypot provider is `togetherai`, the correct key is `TOGETHER_AI_SECRET_KEY`. This caused all LLM fallback calls (including MySQL query generation) to fail silently, returning empty responses.
- **Fix in `main.py:write_cowrie_cfg()`** — API key resolution now mirrors `llm_client.py:get_hp_client()`: falls back to the provider-specific env var (`TOGETHER_AI_SECRET_KEY` for togetherai) when `config.llm_api_key_hp` is empty. The resolved key is written directly to `cowrie.cfg`.
- **Fix in `Blue_Lagoon/honeypot_tools.py`** — `_compose_env()` now resolves the API key using `_PROVIDER_ENV_KEYS` instead of always using `OPENAI_API_KEY`, ensuring the Docker compose env var also carries the correct key.
- **Result**: MySQL queries (`SHOW DATABASES`, `SELECT * FROM wp_users`, etc.) now return real data from the honeypot DB container. Honeypot LLM token usage went from 0/0 to 4,565/593 tokens.

### Anti-Loop State Register (`Sangria/attack_state.py`)

- **Commands-executed tracking** — New `commands_executed` list and `_seen_commands` dedup set track every unique (host, command) pair the attacker has run. Injected into the system prompt as `COMMANDS ALREADY EXECUTED (do NOT repeat these):` with up to 30 recent entries. Skips short interactive responses (passwords, "yes", "exit"). Capped at 50 entries.
- **DB credential "used" marking** — `_parse_db_access()` now extracts `-u USER` and `-pPASSWORD` from mysql/psql commands and marks matching credentials as `[USED]`. Previously, DB credentials always showed `[UNUSED]` in the state register even after the attacker connected, causing the model to re-attempt database access on every loop cycle.
- **Serialization** — `to_dict()` now includes `commands_executed` for JSON logging.

### History Window Increase (`config.py`)

- `history_window` changed from 10 to 20. With the smaller window, Llama 3.3 70B entered deterministic 10-command loops due to amnesia. The wider window combined with the commands-executed tracking should significantly reduce repetition.

### DB Container on Hop1 (`config.py`)

- `chain_db_enabled` changed from `[False, True, False]` to `[True, True, False]`. In honeynet mode, hop1 (wordpress_server) previously had no MySQL container, causing all SQL queries to return `ERROR 2003 (HY000): Can't connect to MySQL server`. The attacker detected this inconsistency and terminated with `success: false`. Hop1 already had a matching `db_config.json`.

### MySQL Prompt Pattern Fix (`Sangria/terminal_io.py`) *(from late 2026-03-17)*

- Added `mysql> ` and `mysql [db]> ` to `prompt_patterns` so pexpect can detect MySQL client prompts instead of timing out with ^C.

### Credential Regex Tightening (`Sangria/attack_state.py`) *(from late 2026-03-17)*

- Password credential regex now uses negative lookahead to exclude nsswitch.conf values (`files`, `compat`, `nis`, `dns`, `db`, `systemd`) and requires minimum 3 characters.

### Profile Enrichment (`Reconfigurator/profiles/wordpress_server.json`) *(from late 2026-03-17)*

- Added `/home/deploy/.bash_history` with 18 realistic sysadmin commands.
- Added `/etc/apache2/`, `/etc/mysql/`, `/etc/php/`, `/etc/letsencrypt/` directory tree entries.
- Added file_contents for `wordpress.conf` (Apache VirtualHost) and `mysqld.cnf` (MySQL config).

---

## 2026-03-17 — Terminal Robustness, LLM Guardrails, Graceful Bailout

### Password Echo Sync Fix (`Sangria/terminal_io.py`)

- **Auto-detect password mode** — Added `_last_matched_idx` module-level state that tracks the last matched prompt pattern. When the previous command ended on a password prompt (indices 7 or 8 in `prompt_patterns`), the next `send_terminal_command` call auto-enables `password_mode`, skipping echo sync. Prevents the echo sync from consuming `root` inside `root@hostname:~#` and causing a 40s timeout.
- **Fingerprint branch stores matched index** — The SSH fingerprint auto-accept path now reassigns `matched_idx` from the second `expect()` call so the stored index reflects the actual final prompt.
- **Reset on timeout recovery** — `_recover_from_timeout` resets `_last_matched_idx = None` since terminal state is unknown after recovery.

### Continuation Prompt Detection (`Sangria/terminal_io.py`)

- **Added `> $` to `prompt_patterns`** (index 13) — Detects bash continuation prompts (unmatched quotes, heredocs) immediately instead of waiting 40s for timeout. When matched, sends Ctrl+C to cancel the malformed command and waits for a shell prompt.
- **Multiline command compatibility** — `_send_multiline_command` excludes `_IDX_CONTINUATION` from "final prompt" detection so heredoc/multiline sends still work correctly.

### Less Destructive Timeout Recovery (`Sangria/terminal_io.py`)

- **Two-stage recovery** — `_recover_from_timeout` now tries Ctrl+C alone first (preserves nested SSH sessions). Only escalates to Enter + Ctrl+C if the gentle attempt doesn't produce a prompt within 5s.
- **No more pre-emptive `\r`** — Removed the Enter press before Ctrl+C that was causing duplicate command submissions in Cowrie logs and shell corruption.

### Trailing Quote Sanitizer (`Sangria/llm_tools.py`)

- **`_fix_unmatched_quotes()`** — Detects trailing unmatched `'` or `"` (e.g., `2>/dev/null'`) and strips them before sending to terminal. Emits a warning when it fixes a command. Skipped for password inputs.

### Ctrl+C Interception (`Sangria/llm_tools.py`, `Sangria/terminal_io.py`)

- **`send_ctrl_c()` helper** — New function in `terminal_io.py` that sends Ctrl+C via `sendcontrol('c')` and waits for a prompt.
- **Literal `\x03` detection** — `terminal_tool()` in `llm_tools.py` detects when the LLM sends `\x03` as input and routes it through the control channel instead of `sendline`, preventing SSH session kills.

### Empty Tool Call Nudge (`Sangria/sangria.py`)

- **Consecutive empty call detection** — Tracks `empty_streak` counter. After 2 consecutive empty `{}` tool calls, injects a user-role nudge message ("Run a command or call terminate") into the conversation and resets the counter.

### Graceful Ctrl+C Bailout (`Sangria/sangria.py`, `main.py`, `Sangria/display.py`)

- **`KeyboardInterrupt` in attack loop** — `run_single_attack` catches Ctrl+C inside the main loop, sets `aborted=True`, and breaks cleanly. Post-loop finalization (JSON log, attack state, cost summary) always runs.
- **Return value extended** — `run_single_attack` now returns `(logs, tokens, aborted)` 3-tuple.
- **`main_single` and `main_honeynet` bailout** — Both session loops unpack the `aborted` flag. On abort, post-session steps (extract_session, format_session_report, save tokens) still run before breaking. The `.md` report is always generated.
- **`print_bailout()`** — New display function showing yellow banner: "SESSION ABORTED (Ctrl+C) — saving logs..."

### Config Sync Fix (`main_menu.py`)

- **In-memory config update** — `apply_partial_config()` now syncs the live `config` module via `setattr()` after writing to disk. Fixes bug where `experiment_name` (and other settings) from the previous experiment leaked into the next one because Python's cached module still had the old values.

## 2026-03-16 — Long Run Fixes + SCP Two-Direction Simulation + Remote Files

### Long Run Fixes (from 200-iteration test findings)

- **ANSI escape stripping** (`Sangria/attack_state.py`) — Added `_ANSI_RE` regex and `_strip_ansi()` helper. Applied in `_update_current_host()` and `_extract_credentials_regex()` to prevent ANSI color codes from corrupting hostname tracking and credential extraction.
- **Log file overwrite fix** (`Sangria/sangria.py`) — Final trimmed message window now saves to `.final.json` instead of overwriting the incremental `.json` log. Both files coexist: `attack_1.json` (full history) + `attack_1.final.json` (last window).
- **SSH reconnection prompt** (`Sangria/attacker_prompt.py`) — Added reconnection guidance to the base prompt's situational awareness section and to Llama, DeepSeek, and Qwen model-specific addenda. Instructs the LLM to SSH back instead of terminating when a connection drops.
- **Thorough exploitation enabled** (`config.py`) — `thorough_exploitation_prompt` set to `True` by default.
- **Failed attempts cleanup** (`Sangria/attack_state.py`) — Successful SSH now clears prior failed attempts for that host IP from the `failed_attempts` list.
- **New tests** (`Tests/test_attack_state.py`) — 5 new tests: ANSI stripping in hostnames, ANSI stripping in credentials, DEC private mode stripping, SSH success clears failures, SSH success preserves other hosts' failures.

### SCP Two-Direction Simulation — Phase 1 (`Cowrie/cowrie-src/src/cowrie/commands/scp.py`)

- **Fixed direction detection** in `start()` — scans ALL args for `[user@]host:path` pattern, not just the last arg. Remote in last position = push (existing), remote elsewhere = pull (new).
- **New `_handle_pull_remote()` method** — parses `user@host:path`, checks `/etc/hosts` for known hosts, simulates transfer with progress bar, creates stub file in VFS via `fs.mkfile()`. Unknown hosts get fast `Connection refused` instead of hanging.

### SCP Two-Direction Simulation — Phase 2 (Remote File Content)

- **Schema** (`Reconfigurator/RagData/filesystem_profile_schema.json`) — Added optional `remote_files` property: nested object keyed by host, then by remote path, with `content_type` (text/binary), `content`, `size`, `description` fields.
- **Pipeline scanner** (`Reconfigurator/new_config_pipeline.py`) — `_scan_remote_file_refs()` scans `file_contents` for `scp`/`rsync` `user@host:/path` patterns, filters to known `/etc/hosts` entries, populates `remote_files` in `finalize_profile()`.
- **LLM prompt** (`Reconfigurator/new_config_pipeline.py`) — `build_profile_prompt()` now instructs the LLM to generate `remote_files` with text content for any SCP/rsync references in scripts.
- **Deterministic fallback** (`Reconfigurator/new_config_pipeline.py`) — `_enrich_remote_files()` fills missing content using filename-pattern templates: `.sql` (MySQL dump with creds), `credentials.xml` (Jenkins-style), `.conf`/`.cfg`/`.cnf` (INI with DB+Redis creds), `.env` (env vars with AWS keys), `.yml`/`.yaml` (Docker Compose), `.sh` (backup script with MYSQL_PWD), `.log` (timestamped backup log). Binary extensions (.gz, .tar, .zip) left as stubs.
- **Converter** (`Reconfigurator/profile_converter.py`) — `generate_remote_files()` writes text content to `honeyfs/_remote/<host>/<path>`, generates gzip stubs for binary files, builds `etc/remote_files.json` index. Called from `deploy_profile()`.
- **SCP handler** (`Cowrie/cowrie-src/src/cowrie/commands/scp.py`) — `_handle_pull_remote()` updated with `_load_remote_files_index()` to load the index, serve real content from honeyfs, set `A_REALFILE` pointers so `cat` works on pulled files. Progress bar shows realistic MB/KB sizes.
- **All 13 profiles enriched** — Every profile now has `remote_files` entries with text content matching each remote host's role (DB credentials, Jenkins XML, LDAP configs, Redis configs, mail relay creds, etc.). 126 total remote files across all profiles, 120 with real text content.

### HoneyNet Settings Menu (`main_menu.py`)

- **New "HoneyNet" option** in settings menu — between "Attacker Options" and "CHeaT Defenses".
- **`settings_honeynet()`** — toggle `honeynet_enabled`, configure chain profiles interactively.
- **`_configure_chain_profiles()`** — select number of hops (1-10), pick profile per hop from available profiles, toggle per-hop database honeypot.
- **`_write_chain_config()`** — writes `chain_profiles` and `chain_db_enabled` lists to `config.py`.
- **`view_current_settings()`** — now shows HoneyNet status, hop profiles, and DB flags.

### Docs Moved

- `docs/doing/long-run-findings.md` → `docs/done/`
- `docs/doing/long-run-fixes-design.md` → `docs/done/`
- `docs/doing/scp-fix-design.md` → `docs/done/`

## 2026-03-15g — P3 Command Handlers: journalctl, docker, vim/nano

### Fix 13: vim/nano Editor Simulation (P1 — upgraded)
- **New: `vim.py`** — `Command_vim` shows real file contents from honeyfs in vim-like format (line count, `~` padding, status line). Accepts `:q`, `:wq`, `:q!`, `ZZ`, `:w` commands. `Command_nano` shows file with GNU nano header/footer and keybinding bar. Exit via Ctrl-C/Ctrl-D (Ctrl-X not available in Cowrie's key dispatch).

### Fix 11: Native `journalctl` Handler (P2 — upgraded)
- **New: `journalctl.py`** — reads log file content from honeyfs via `_SERVICE_LOG_MAP` (maps service names to log paths like `/var/log/auth.log`, `/var/log/backup.log`). Falls back to generated template entries from profile services. Supports `-u <unit>`, `-f` (follow/hang), `-n <lines>`, `-xe`, `--disk-usage`, `--since`.

### Fix 12: Native `docker` Handler (P2)
- **New: `docker.py`** — reads containers from profile docker-compose files (same parsing as `prequery.py`). Falls back to deriving containers from profile services with known Docker images. Supports `ps`, `images`, `logs`, `inspect`, `version`, `info`, `node ls`, `service ls`, `network ls`, `compose ps/logs`. Mutating commands (`exec`, `run`, `build`) fall through to LLM fallback. `docker-compose` (v1 binary) registered as alias.

## 2026-03-15f — Cowrie Command Authenticity Fixes (P0 + P1 + P2)

Implemented 7 fixes from `docs/doing/COWRIE_AUTHENTICITY_FIXES.md` to make Cowrie command output consistent with deployed profiles.

### Fix 1: Profile-Aware `ps` Output (P0)
- **New: `generate_cmdoutput()`** in `profile_converter.py` — generates `cmdoutput.json` from profile services with realistic VSZ/RSS values
- **Modified: `deploy_profile()`** — now calls `generate_cmdoutput()` as step 7
- **Modified: `_write_cowrie_cfg()`** in `main.py` — sets `[shell] processes = share/cowrie/cmdoutput.json`
- Native `Command_ps` now shows profile services instead of hardcoded fallback

### Fix 2: Profile-Aware `crontab -l` (P0)
- **Modified: `crontab.py`** — `-l` flag reads `crontabs` from profile via `llm_fallback_handler._profile`. Falls back to "no crontab" if profile has no entry for the user.

### Fix 3: Native `ss` Handler (P1)
- **New: `ss.py`** — reads profile services, supports `-t`, `-u`, `-l`, `-n`, `-p`, `-a`, `-h` flags. Output format matches real `ss` (Netid/State/Recv-Q/Send-Q columns, `users:((prog,pid=N,fd=3))` process format).

### Fix 4: Native `systemctl` Handler (P1)
- **New: `systemctl.py`** — supports `status`, `list-units`, `start/stop/restart/enable/disable`, `is-active`, `is-enabled`, `--version`. Reads services from profile with loose name matching (e.g., `ssh` matches `sshd`).

### Fix 5: Filesystem-Aware `head` and `tail` (P1)
- **New: `head.py`** — `Command_head` and `Command_tail` using same `fs.file_contents()` pattern as `cat.py`. Supports `-n N`, `-f` (tail hangs until Ctrl-C), `-q`, multi-file headers.

### Fix 8: `id` with Group Memberships (P2)
- **Modified: `base.py`** — `Command_id` reads user's groups from profile, maps to known GIDs (sudo=27, docker=999, etc.).

### Fix 6: Filesystem-Aware `grep` (P2)
- **New: `grep.py`** — walks pickle filesystem + honeyfs to search actual file contents. Supports `-i`, `-r`/`-R`, `-l`, `-n`, `-c`, `-v`, `-w`, `-H`/`-h`, `-e`, `--include`, `--exclude`. Piped input works too.

### Fix 7: Profile-Aware `df -h` (P2)
- **Modified: `generate_txtcmds()`** in `profile_converter.py` — reads optional `disk_layout` field from profile. Computes avail/use% from size/used. Falls back to generic layout if field absent.

### Fix 9: `du -sh` Filesystem-Aware (P2)
- **Modified: `du.py`** — `_dir_size()` recursively sums `A_SIZE` from pickle fs entries. Supports `-s` (summary), `-h` (human-readable), `-c` (total). Shows subdirectory sizes when not in summary mode.

### Fix 10: `service --status-all` from Profile (P2)
- **Modified: `service.py`** — `status_all()` reads profile services instead of hardcoded desktop-oriented list. Base system services (cron, dbus, rsyslog, etc.) always shown.

## 2026-03-15e — OpenAI Tool-Calling Correctness Fixes

Three fixes to `Sangria/llm_tools.py` and `Sangria/sangria.py` for API message hygiene.

### Modified: `Sangria/llm_tools.py`

- **`terminate` strict mode** — Added `strict: True` and `additionalProperties: False` for OpenAI provider, matching the existing `terminal_input` schema.

### Modified: `Sangria/sangria.py`

- **`honeypot_logs` leak** — No longer injected into the `tool_response` dict that goes into `messages` (and gets sent to the API). A separate `log_entry` dict carries `honeypot_logs` and `name` for the file log only.
- **Deprecated `name` field** — Removed from `tool_response`. Kept in `log_entry` for file log debugging.

## 2026-03-15d — Model-Specific Attacker Prompts

Added model family classification and per-model prompt addenda to `Sangria/attacker_prompt.py`, fixing premature termination and model-specific behavioral issues (tool name hallucination, command looping, skipping file reads).

### Modified: `Sangria/attacker_prompt.py`

- **Model family classifier** — `_get_model_family()` maps `config.llm_model_sangria` to one of `openai`, `llama`, `deepseek`, `qwen`, or `default`. Branches on model name (not provider), so a Llama model on Together AI gets Llama guidance.
- **Thorough exploitation section** (all models) — Checklist of credential locations to check before terminating: config files, `.env`, SSH keys, bash history, mail spools, database contents. Instructs separate `find` commands (no `-o` flag) so Cowrie's native `find` handler runs them.
- **Llama addendum** — Anti-loop rules (no re-SSHing, no repeating commands), correct tool name (`terminal_input`), mandatory file reading after `ls`/`find`, mental checklist.
- **DeepSeek addendum** — Forces tool calls over verbose reasoning, correct tool name, no command repetition.
- **Qwen addendum** — Same anti-loop rules as Llama, explicit tool argument names.
- **OpenAI addendum** — Empty (existing prompt works well, no changes needed).
- **Default addendum** — Conservative subset of rules for unknown models.
- **No breaking changes** — `get_prompt()` signature unchanged. OpenAI models get the same base prompt plus only the shared thorough exploitation section.

## 2026-03-15c — Native MySQL Command Handler

Added a native Cowrie command handler for `mysql`, fixing silent failures when attackers run `mysql -u root -p` inside the honeypot.

### New File: `Cowrie/cowrie-src/src/cowrie/commands/mysql.py`

- **Interactive password prompt** — Uses the same `password_input` + `callbacks` pattern as `ssh.py`/`su.py`. Handles real MySQL's `-p` quirk: `-pPASSWORD` (no space) is an inline password, `-p` alone prompts interactively.
- **`mysql>` shell loop** — After login, prints a MySQL banner (version pulled from profile services) and enters a recursive callback loop for SQL input.
- **`USE db` prompt tracking** — Prompt updates to `mysql [dbname]>` after `USE` statements.
- **LLM routing** — Each SQL line is sent to the LLM fallback handler as `mysql -e '<sql>'`, triggering the existing `db_context` prequery pipeline with credential injection.
- **Inline `-e` queries** — `mysql -e 'SELECT ...'` executes immediately without entering interactive mode.
- **Async guard** — Sets `self._llm_pending` and `self.protocol.llm_pending` to prevent input during LLM calls.
- **Flag parsing** — Supports `-u`, `-p`, `-h`, `-D`, `-e`, `--help`, `--version`.
- **Registered** as `/usr/bin/mysql`, `/usr/local/bin/mysql`, and `mysql`.

### Modified: `Cowrie/cowrie-src/src/cowrie/commands/__init__.py`

- Added `"mysql"` to `__all__`.

## 2026-03-15b — Token Savings: Followup Toggle, Output Truncation, Attack State Register

Implemented all four opportunities from `TOKEN_SAVINGS.md`, reducing per-session prompt token usage by ~47% immediately and up to ~92% for deep sessions when history trimming is enabled.

### Opportunity 1: Followup Call Toggle (`Sangria/sangria.py`, `config.py`)

- **`config.py`** — Added `followup_enabled = False`. The redundant follow-up LLM call after every tool execution is now off by default. Set `True` to restore old behavior.
- **`Sangria/sangria.py`** — Wrapped the follow-up block (lines 176–218) with `if tool_use and config.followup_enabled:`. Added fallback per-iteration timing when followup is disabled.
- **Savings:** ~47% of prompt tokens, ~50% of API calls, ~30-40% wall-clock time per session. The follow-up calls produced almost no useful content (2 messages out of 10 calls in the measured session).

### Opportunity 2: Attack State Register + History Trimming (`Sangria/attack_state.py` new, `Sangria/sangria.py`, `config.py`, `main.py`)

- **New `Sangria/attack_state.py`** — `AttackStateRegister` class providing structured attacker memory across long sessions. Tracks five categories: hosts (IP, hostname, access level, method), credentials (with source file and used/unused status), files with secrets, discovered services, and failed attempts. Profile-aware credential detection (zero false positives for files in the honeypot profile) with regex fallback for lateral-movement hosts. Deduplication and 50-entry cap per category. `to_prompt_string()` produces ~300-500 token summary regardless of session depth. `to_dict()` for JSON logging.
- **`Sangria/sangria.py`** — State register initialized with honeypot profile at session start. `update_from_tool_call()` called after every tool execution. System prompt rebuilt each iteration with current state when `history_window > 0`. Sliding window trims messages beyond the window size (system prompt + last N messages kept). Attack state saved to `attack_state_N.json` alongside session logs.
- **`config.py`** — Added `history_window = 0` (disabled by default for safe rollout; set to 10-20 to enable trimming).
- **`main.py`** — Both `main_single()` and `main_honeynet()` call sites pass `profile=` to `run_single_attack`.
- **Savings (with `history_window = 10`):** 17% at 10 iterations, 75% at 50, 86% at 100, 92% at 200.

### Opportunity 3: Tighter Output Truncation (`Sangria/terminal_io.py`, `Sangria/attacker_prompt.py`)

- **`Sangria/terminal_io.py`** — Reduced command output truncation threshold from 10,000 → 5,000 characters.
- **`Sangria/attacker_prompt.py`** — Updated the truncation limit reference in the attacker system prompt to match (10000 → 5000).
- **Savings:** ~10-20% for sessions with verbose commands (nmap, find, cat on large files).

### Docs

- Moved `TOKEN_SAVINGS.md` and `ATTACK_STATE_REGISTER.md` from `docs/doing/` to `docs/done/`.

---

## 2026-03-15 — Together AI Provider Support, Cost Tracking, Llama 3.3 Compatibility

Added Together AI as an LLM provider, per-session cost analysis (attacker + honeypot defender), and numerous compatibility fixes for running the attack loop with non-OpenAI models (Llama 3.3 70B).

### Together AI Provider (`Utils/llm_client.py`, `config.py`, `Sangria/model.py`)

- **`Utils/llm_client.py`** — Added `togetherai` to `_PROVIDER_URLS` (`https://api.together.xyz/v1`). New `_PROVIDER_ENV_KEYS` mapping so `get_client()` and `get_hp_client()` resolve `TOGETHER_AI_SECRET_KEY` env var when provider is `togetherai`.
- **`Sangria/model.py`** — Added Together AI models to `LLMModel` enum (function-calling supported only): `LLAMA_4_MAVERICK`, `LLAMA_3_3_70B`, `QWEN_3_5_397B`, `DEEPSEEK_V3`, `DEEPSEEK_R1`.
- **`config.py`** — Provider comments updated to include `togetherai`.

### Together AI Menu Integration (`main_menu.py`)

- **Provider selection** — "Together AI" added to both host and honeypot provider dropdowns. Cloud providers (`openai`, `togetherai`) skip localhost→`host.docker.internal` URL rewriting.
- **Model selection** — Provider-aware model picker via `_MODEL_MENUS` dict. Together AI shows Llama 3.3 70B (Recommended), Llama 4 Maverick, Qwen 3.5, DeepSeek V3/R1. OpenAI shows GPT-4.1 variants.
- **Model persistence** — `model_mapping` in `apply_partial_config()` now includes all Together AI enum members. Previously only OpenAI models were mapped, causing Together AI selections to be written as plain strings instead of `LLMModel.*` references.
- **Display fixes** — `view_current_settings()` now uses `getattr(m, "value", m)` to show actual model IDs instead of `LLMModel.LLAMA_3_3_70B`. API key line shows `TOGETHER_AI_SECRET_KEY` for togetherai provider.

### Per-Session Cost Analysis (Attacker + Honeypot Defender)

- **`Sangria/sangria.py`** — Added Together AI pricing to `MODEL_PRICING` dict (Llama 3.3 70B: $0.88/$0.88, Maverick: $0.27/$0.85, DeepSeek V3: $0.60/$1.70, DeepSeek R1: $3.00/$7.00, Qwen 3.5: $0.10/$0.15 per 1M tokens). Made `prompt_tokens_details` access null-safe (`_details.cached_tokens if _details else 0`) since Together AI doesn't return cached token details.
- **`Cowrie/.../shell/llm_fallback.py`** — New `_append_token_usage()` static method on `HybridLLMClient`. After each LLM response, extracts `usage` from the API JSON and appends a JSONL entry (`prompt_tokens`, `completion_tokens`, `cached_tokens`, `timestamp`) to `/cowrie/cowrie-git/var/llm_tokens.jsonl` (volume-mapped to host).
- **`main.py`** — New `read_and_reset_hp_tokens()` reads the honeypot JSONL token log, sums tokens, calculates cost using `MODEL_PRICING`, and truncates the file. Called after every session in both single and honeynet modes. Merges 5 new fields into `tokens_used`: `honeypot_prompt_tokens`, `honeypot_completion_tokens`, `honeypot_cached_tokens`, `honeypot_cost_usd`, `total_cost_usd`.
- **`Blue_Lagoon/honeypot_tools.py`** — `clear_hp_logs()` now also truncates `llm_tokens.jsonl` alongside the Cowrie JSON log (both single and honeynet modes).
- **`Sangria/display.py`** — New `print_honeypot_cost()` and `print_total_cost()` functions. Shows attacker/defender/total cost breakdown in bordered magenta boxes after each session.
- **`Sangria/session_formatter.py`** — Replaced simple token count lines with full **Cost Analysis** table in Markdown reports: Attacker (Sangria) row, Defender (Honeypot) row, and Total row, each with prompt/completion/cached tokens and USD cost.

### Llama 3.3 Compatibility Fixes

- **Tool schema optimization (`Sangria/llm_tools.py`)** — New `_build_tools()` factory adapts schemas per provider. OpenAI: strict mode with full 378-element MITRE technique enums. Non-OpenAI: free-text tactic/technique fields with examples, no `strict`/`additionalProperties`. Reduces tool schema from ~14k to ~1.5k chars per call, giving the model much more context for the actual conversation.
- **Hallucinated tool name mapping (`Sangria/llm_tools.py`)** — Llama 3.3 invents tool names like `send_password`, `run_command`, `send_input`. New `_TERMINAL_ALIASES` set maps these to `terminal_input`. Last-resort fallback: any unknown tool with input-like args (`input`, `command`, `password`, `text`) is treated as `terminal_input`.
- **Empty args handling (`Sangria/llm_tools.py`)** — `terminal_tool()` no longer raises `ValueError` on empty args; sends an empty line instead so the model can self-correct.
- **Follow-up call provider awareness (`Sangria/sangria.py`)** — OpenAI: follow-up called without tools (pure narrative). Non-OpenAI: follow-up called WITH tools so Llama can respond properly. If follow-up returns tool calls, only the text content is appended (tool calls are dropped to avoid unexecuted calls in history).

### SSH Fingerprint Auto-Accept (`Sangria/terminal_io.py`)

- **`send_terminal_command()`** — When pexpect matches the SSH fingerprint prompt (`Are you sure you want to continue connecting`) or retry prompt (`Please type 'yes', 'no'`), automatically sends `"yes"` and continues waiting for the next prompt. Models no longer need to handle fingerprint confirmation, eliminating the infinite loop where Llama 3.3 kept sending `root` instead of `yes`.
- Added `_IDX_FINGERPRINT` and `_IDX_FINGERPRINT_RETRY` index constants for the auto-accept patterns.

### Pexpect Echo Handling Fixes (`Sangria/terminal_io.py`)

- **Partial echo tail stripping** — `_strip_command_echo()` now detects and strips partial echo remnants from command output. When `expect_exact` only consumes the first 40 chars of a command echo (e.g. `find /home -type f -name '*.txt' 2>/dev/null`), the remaining tail (`null`, `2>/dev/null`) leaked into the output, confusing the attacker model. New Case 2 logic checks if the first output line is a suffix of the original command and strips it.
- **`ECHO_MATCH_LEN` constant** — Extracted the hardcoded `[:40]` echo match limit into a named constant. All three echo match sites (`send_terminal_command`, `_send_multiline_command`) now reference `ECHO_MATCH_LEN`.
- **Password mode (`password_mode` flag)** — New `password_mode` parameter threaded through `send_terminal_command()` → `terminal_input()` → `terminal_tool()`. When the attacker model calls `send_password` (hallucinated tool), echo sync is skipped entirely. Passwords are not echoed by terminals, so `expect_exact("root")` would accidentally consume the `root` in `root@hostname:~#`, causing the prompt pattern match to fail and triggering a 40-second timeout. Detected via `_PASSWORD_ALIASES` set in `handle_tool_call()` and via `password` key detection in `terminal_tool()`.

### Bug Fixes

- **Profile browser crash (`main_menu.py`)** — `_discover_profiles()` now skips JSON files whose top-level value is a list (e.g. `*_lure_chains.json`, `.backup_*` files), fixing `'list' object has no attribute 'get'` error.
- **CHeaT checkbox crash (`main_menu.py`)** — `_cheat_toggle_techniques()` replaced invalid `default=current` list parameter with `questionary.Choice(..., checked=...)` per item, fixing `ValueError` when no techniques were enabled.
- **MySQL 8.0 init SQL crash (`Reconfigurator/db_seed_generator.py`)** — Replaced `DEFAULT '0000-00-00 00:00:00'` with `DEFAULT CURRENT_TIMESTAMP` (3 occurrences). MySQL 8.0 strict mode rejects zero-date defaults, causing the `honeypot-db` container to exit on startup.
- **DB wait timeout (`Blue_Lagoon/honeypot_tools.py`)** — `wait_for_db()` now checks `State.Running` before polling health check. Detects crashed containers immediately instead of blocking 60 seconds.
- **`_prompt_model` cancellation (`main_menu.py`)** — Model selection loop now skips fields where `questionary.select().ask()` returns `None` (user pressed Escape), preventing `"None"` from being written to config.

---

## 2026-03-14 — CHeaT Defense System + Terminal Display Overhaul

Integrated proactive LLM attacker detection techniques inspired by the CHeaT (Cloak, Honey, Trap) USENIX Security 2025 paper. Also overhauled the Sangria attack loop terminal output with colored, bordered display elements.

### CHeaT Defense System (`Reconfigurator/cheat/`)

- **New `Reconfigurator/cheat/unicode_tokens.py`** — Unicode honeytoken credential generation using three methods: backspace injection (`\b`), Unicode tag characters (U+E0041–E007A), and soft hyphen (`\u00ad`). Each method creates passwords that LLMs and humans parse differently, enabling automated attacker detection. `apply_honeytokens_to_profile()` injects honeytokens into SSH accepted_passwords and credential-bearing files.
- **New `Reconfigurator/cheat/canary_urls.py`** — Honey URL generation planted in `.bash_history`, README files, config comments, and cron entries. URLs use realistic internal-looking domains derived from the profile hostname. If an attacker fetches them (via curl/wget), it confirms automated behavior. `apply_canary_urls_to_profile()` injects URLs into profile `file_contents`.
- **New `Reconfigurator/cheat/payload_templates.py`** — Prompt injection payloads (task_complete, fake_system, honey_note, misdirection, halt) that hijack LLM instruction flow when read from honeypot files. Payloads are wrapped for file type (HTML comments, `#` comments, log format). `apply_prompt_traps_to_profile()` injects payloads into profile `file_contents`.
- **New `Reconfigurator/cheat/tool_traps.py`** — Trap payloads appended to Cowrie txtcmd outputs: misdirect (fake ports in netstat/ps), overwhelm (20 fake CVEs in dpkg/apt), halt (IDS alert messages), canary (update script URLs). `apply_tool_traps_to_txtcmds()` modifies txtcmd files on disk after deployment.

### CHeaT Detection Pipeline (`Purple/cheat_detector.py`)

- **New `Purple/cheat_detector.py`** — `CheaTDetector` class that analyzes post-session Cowrie logs against planted defenses. Checks credential usage (matches against honeytoken LLM/human/original variants), canary URL access (scans commands for planted URLs), and prompt trap effectiveness (heuristic behavioral change detection). Computes weighted `llm_confidence_score` (unicode=0.4, canary=0.2, prompt=0.15 per token).

### CHeaT Integration (`main.py`, `config.py`, `main_menu.py`)

- **`config.py`** — Added 6 CHeaT toggles: `cheat_enabled` (master), `cheat_unicode_honeytokens`, `cheat_canary_urls`, `cheat_prompt_traps`, `cheat_tool_traps`, `cheat_overwhelm`.
- **`main_menu.py`** — Added "CHeaT Defenses" settings submenu with master toggle, checkbox-based technique selection, enable/disable all, and technique descriptions. Updated `view_current_settings()` to show CHeaT status.
- **`main.py`** — Added `apply_cheat_defenses()` helper that applies all enabled defenses to profiles before deployment and tool traps after deployment. Both `main_single()` and `main_honeynet()` run CHeaT detection post-session and save `cheat_defenses.json` / `cheat_results.json`. Reconfiguration paths re-apply defenses.

### CHeaT Report Integration (`Sangria/session_formatter.py`)

- **`Sangria/session_formatter.py`** — `format_session_report()` now accepts `cheat_results` parameter. New `_build_cheat_section()` generates Markdown with LLM confidence score, summary table (planted vs triggered per defense type), Unicode Honeytoken Details, Canary URL Access, Prompt Trap Effects, and Behavioral Indicators.

### Terminal Display Overhaul (`Sangria/display.py`)

- **New `Sangria/display.py`** — Centralized terminal display module replacing inline ANSI escape codes. Provides `print_iteration_header()`, `print_attack_banner()`, `print_tool_call()`, `print_tool_response()`, `print_assistant_message()`, `print_followup_message()`, `print_cost_summary()`, `print_termination()`, `print_timing()`, `print_tokens()`. Color scheme: cyan=iteration headers, red=attacker tool calls, green=assistant, blue=follow-up, gray=timing, magenta=cost.
- **`Sangria/sangria.py`** — Replaced all inline `print()` + ANSI escape codes with `display.*` calls. Fixed pre-existing curly quote unicode issue (U+2018/U+2019 → straight quotes).
- **`Sangria/terminal_io.py`** — Command timing output now uses `display.print_command_timing()`.

### Tests

- **New `Tests/test_cheat.py`** — 24 tests covering all CHeaT phases: unicode token generation (3 methods), profile application, detector (no defenses, LLM/human credential match, canary URL detection, prompt trap effects), report formatting, canary URL generation/application, prompt trap wrapping/HTML injection, tool trap generation/application.

### Documentation

- **New `docs/CHEAT_IMPLEMENTATION_PLAN.md`** — 7-phase implementation plan with architecture overview, config design, code structure, integration points, and implementation order.

---

## 2026-03-13 — Architecture Overhaul: Direct Cowrie Integration, LLM Abstraction, Demo Mode

Major refactor replacing the Beelzebub-based honeypot with direct Cowrie container management, adding multi-provider LLM support, a demo mode, an interactive settings menu, and numerous Sangria/Reconfigurator improvements.

### Architecture: Cowrie-Native Honeypot

- **Replaced Blue_Lagoon/Beelzebub with direct Cowrie** — `docker-compose.yml` now runs a `cowrie` service (built from `Cowrie/cowrie-src`) instead of `blue_lagoon`. Config volumes mount `cowrie_config/` directly into the container (`etc/`, `honeyfs/`, `share/`, `var/`). Environment passes `COWRIE_HYBRID_LLM_*` and `COWRIE_DB_*` vars. Exposes SSH on port `22${RUNID}` for demo mode.
- **`main.py` rewritten** — New `deploy_cowrie_config()` takes a parsed profile dict and deploys it to `cowrie_config/` (or `cowrie_config_hop{N}/` for honeynet). Writes `cowrie.cfg` via `_write_cowrie_cfg()` with hybrid LLM enabled, shell/SSH/logging sections, and local-model Docker networking support (`host.docker.internal` rewriting). Integrates DB seed pipeline (`extract_db_config` → `generate_init_sql` → `write_db_init_scripts` → `generate_db_compose`). Split `main()` into `main_single()` and `main_honeynet()`.
- **`Blue_Lagoon/honeypot_tools.py` expanded** — Added `_compose_env()` (injects DB vars from `db_config.json`), `_compose_files()` (returns override/honeynet compose flags), `generate_db_compose()` / `remove_db_compose()`, `wait_for_db()`, `get_new_hp_logs()` with byte-offset tracking, `get_cowrie_log_path()`, per-hop offset tracking (`_hop_offsets`), `wait_for_all_cowrie()`, `stop_single_hop()`, `start_single_hop()`. Uses `docker-compose` (v1) with explicit `down --remove-orphans` before `up` to avoid stale container metadata crashes.

### LLM Client Abstraction

- **New `Utils/llm_client.py`** — `get_client()` factory returns an `openai.OpenAI` instance routed through the configured provider (`openai`, `ollama`, `vllm`, `lmstudio`, `custom`) based on `config.py` settings. All LLM consumers (Sangria, Terminal IO, Reconfigurator) now use this instead of creating their own clients.
- **New `Utils/llm_cache.py`** — Host-side LLM response cache utility for demo mode. Provides `normalize_cache_key()`, `compute_profile_hash()`, and load/save helpers for the Cowrie-side cache file.

### Config Overhaul (`config.py`)

- Added separate LLM provider settings: `llm_provider` / `llm_base_url` / `llm_api_key` for host-side, and `llm_provider_hp` / `llm_base_url_hp` / `llm_api_key_hp` for the Docker-side honeypot LLM.
- Renamed `llm_model_blue_lagoon` → `llm_model_honeypot`.
- Added `initial_profile` (path to starting filesystem profile), `profile_novelty_threshold`, `provide_nonroot_credentials`, `confirm_before_session`.
- Added HoneyNet settings: `honeynet_enabled`, `chain_profiles`, `chain_db_enabled`.
- Added DB honeypot constants: `DB_CONTAINER_IP_SUFFIX`, `DB_MYSQL_IMAGE`, `DB_POSTGRES_IMAGE`, `DB_ROOT_PASSWORD`, `DB_PROXY_TIMEOUT`.
- Default `reconfig_method` changed to `NO_RECONFIG`.

### Demo Mode

- **New `demo.py`** — `DemoRunner` (single-pot) and `HoneyNetDemoRunner` (multi-hop) for scripted showcase sessions. Deploys profiles, starts containers, runs a curated SSH session against Cowrie with typewriter effects and configurable speed.
- **Main menu integration** — "Demo Mode" option in main menu with profile selection, preset HoneyNet chains (WordPress→Database→CI/CD, etc.), and speed selection (normal/fast/interactive).

### Interactive Settings Menu (`main_menu.py`)

- Added "Settings" submenu with: View Current Settings, Honeypot Profile (browse/select/preview), Models & Providers, Session Parameters, Reconfiguration, Attacker Options.
- Profile browser discovers and summarizes all JSON profiles in `Reconfigurator/profiles/`.
- Settings changes update `config.py` at runtime.

### Sangria Improvements

- **`attacker_prompt.py`** — New `_pick_credentials()` supports non-root credential provision (random 50/50 root vs non-root when `provide_nonroot_credentials` is True). `get_ssh_port_from_config()` always returns `2222` (Cowrie's actual listen port). Added explicit instructions for SSH host key verification (3-step sequence), interactive prompt handling, situational awareness (check `id` before privesc, use discovered creds immediately, limit pure recon). Target IP switches for honeynet mode.
- **`sangria.py`** — Uses `get_client()` instead of direct `openai.OpenAI()`. Added `MODEL_PRICING` dict and per-session cost estimation. `openai_call()` sets `parallel_tool_calls=False` to prevent buffer desync. Added `[TIMING]` instrumentation for LLM decision, tool execution, and follow-up calls. Follow-up responses now count toward token totals. `total_tokens_used` includes `estimated_cost_usd`.
- **`terminal_io.py`** — New `_drain_buffer()` consumes all pending pexpect data before each command. `_strip_command_echo()` removes terminal echo from output. `_is_multiline()` + `_send_multiline_command()` sends heredocs/multi-line commands line-by-line with continuation prompt handling. Returns structured `{"output": ..., "timing": {...}}` dict. Added `_recover_from_timeout()` shared helper. Additional prompt pattern for non-home-dir Cowrie prompts.
- **`log_extractor.py`** — Replaced `docker logs` subprocess with direct file reading from host-mounted `cowrie.json`. Byte-offset tracking via `_file_offset`. `reset_offset()` syncs with log file state after `clear_hp_logs()`. Filters for `cowrie.command.input` events only. Honeynet mode reads `cowrie_config_hop1/`.
- **`llm_tools.py`** — `retrieve_unique_techniques()` now filters to Linux/Containers/Network Devices platforms only. Tool description specifies "Linux environment".
- **New `Sangria/session_formatter.py`** — Generates Markdown session reports (`attack_N.md`) after each session with command timeline, technique distribution, and token usage.

### Reconfigurator Overhaul

- **`new_config_pipeline.py`** — Complete rewrite. Defines `LURE_REQUIREMENTS` dict with 6 lure categories (breadcrumb_credentials, lateral_movement_targets, privilege_escalation_paths, active_system_indicators, explorable_applications, rabbit_holes) with min counts and validation regexes. Schema loaded once at module level. `query_openai()` uses `get_client()`. New `build_profile_prompt()` generates profiles (not Beelzebub service configs). `validate_lure_coverage()` checks profiles against lure requirements. Removed RAG/embedding pipeline (`retrieve_top_vulns`, `build_llm_prompt`, `SentenceTransformer` dependency). New `sample_previous_profiles()` loads from experiment dirs. `generate_new_profile()` replaces `generate_new_honeypot_config()`.
- **`utils.py`** — Removed `acquire_config_lock()`, `release_config_lock()`, `cosine_similarity()`, `clean_and_finalize_config()`. Kept `extract_json()`.
- **`zeroth_config.py`** — Updated for new pipeline API.
- **New `Reconfigurator/lure_agent.py`** — Lure enrichment agent that extends profiles with additional lure categories and interconnected attack-path chains. Uses `LURE_REQUIREMENTS` and validation from `new_config_pipeline.py`.
- **New `Reconfigurator/profile_distance.py`** — Multi-dimensional Jaccard distance metric between filesystem profiles (OS family, services, lure files, users, ports). Used by `is_novel()` to ensure reconfigured profiles are sufficiently different.
- **`BAAI_bge.py`** — Removed hardcoded Hugging Face token (`hf_mPmpxk...`). Now requires `HF_TOKEN` to be set in environment.

### Purple Module Rename + Metrics

- **Renamed `Purple_Revisited/` → `Purple/`** — All imports updated. New `Purple/metrics/` package with `entropy.py`, `mitre_distribution.py`, `sequences.py`, `session_length.py`. New `Purple/stats_utils.py` and `Purple/utils.py`.
- **`Reconfigurator/criteria/entropy.py`** — Implemented the `session_length` case (was `raise NotImplementedError("My bad lol // Sackarias")`).

### MITRE Technique Filtering

- **`Purple/RagData/retrive_techniques.py`** — `retrieve_unique_techniques()` now accepts `platforms` parameter, filters out deprecated/revoked techniques, and defaults to Linux/Containers/Network Devices when called from `llm_tools.py`.

### Test Updates

- All test imports updated from `Purple_Revisited` → `Purple`.
- `test_metrics_session_length.py` — Fixed assertions for `remove_zeros` parameter: `remove_zeros=False` now correctly includes zero-length sessions, `remove_zeros=True` filters them. Updated edge case tests accordingly.

### Metadata & Cleanup

- **`Utils/meta.py`** — `create_metadata()` records `llm_model_honeypot` and `initial_profile` instead of `llm_model_blue_lagoon` and `llm_provider_hp`.
- Deleted `ANALYSIS_SSH_AND_SUDO_ISSUES.md` and `current_implementation_improvements.md` (stale analysis docs).

---

## 2026-03-06 — 10 New Honeypot Filesystem Profiles

Added 10 new diverse server persona profiles for the Cowrie honeypot reconfigurator, expanding the profile library from 3 to 13. Each profile follows the `filesystem_profile_schema.json` schema and satisfies all 6 lure engagement categories from `LURE_REQUIREMENTS`.

### New Profiles

| Profile | Hostname | OS | Theme |
|---------|----------|----|-------|
| `mail_server.json` | mail-relay-01 | Debian 12.4 | Postfix/Dovecot mail relay with Roundcube webmail |
| `vpn_gateway.json` | vpn-gw-01 | Ubuntu 22.04 | OpenVPN/WireGuard gateway with client configs |
| `monitoring_stack.json` | mon-01 | Ubuntu 22.04 | Grafana/Prometheus/Alertmanager monitoring |
| `file_server.json` | nas-01 | Debian 11.8 | Samba/NFS file shares with credential spreadsheet |
| `dns_server.json` | ns1 | CentOS Stream 9 | BIND DNS with internal zone files (crown jewel) |
| `git_server.json` | git-01 | Rocky Linux 9.3 | Gitea self-hosted Git with LDAP integration |
| `docker_swarm.json` | swarm-mgr-01 | Ubuntu 22.04 | Docker Swarm manager with Traefik reverse proxy |
| `backup_server.json` | backup-01 | Debian 12.4 | Restic/Borg centralized backup with S3 credentials |
| `dev_workstation.json` | dev-ws-03 | Ubuntu 24.04 | Developer VM with AWS/GCP/Stripe/GitHub creds |
| `iot_gateway.json` | iot-gw-01 | Raspbian 11 | MQTT/Node-RED IoT hub on aarch64 with SCADA refs |

### Lure Coverage Per Profile

All profiles pass the following minimum requirements:
- **breadcrumb_credentials** (≥4): Passwords in bash_history, config files, .env, backup scripts
- **lateral_movement_targets** (≥2): /etc/hosts with internal hosts, SSH configs
- **privilege_escalation_paths** (≥1): sudo rules, docker group, writable crons
- **active_system_indicators** (≥3): auth.log, mail, bash_history, /tmp files
- **explorable_applications** (≥1): Service-specific configs and data
- **rabbit_holes** (≥2): Long log files (>500 chars), large configs

### Validation Status

9/10 profiles pass all automated lure checks. 1 remaining fix needed:
- **vpn_gateway**: `explorable_applications` regex match needs adjustment — the `/etc/nginx/conf.d/vpn-portal.conf` path doesn't match the `APP_RE` pattern which looks for `nginx.conf` specifically. Fix: either rename the file path or add an additional matching file.

### Notes

- Profiles are standalone JSON files in `Reconfigurator/profiles/`
- Each profile is 400-600 lines with realistic file contents, credentials, log entries, and configs
- The `dns_server` profile's zone file (~2800 chars) maps 15+ internal hosts — designed as a "crown jewel" lure
- The `iot_gateway` profile uses `aarch64` arch to simulate a Raspberry Pi with OT/SCADA references
- The `backup_server` profile has SSH access to all other servers in its backup script — high-value pivot target

---

## 2026-03-05 — HoneyNet Multi-Hop Architecture

Extended Project Violet from a single Cowrie honeypot to a configurable linear chain of 2-3 interconnected Cowrie containers (HoneyNet). The attacker enters via a weak-password entry pot and must organically discover breadcrumbs to pivot deeper. Goal: maximize attacker dwell time across the chain.

### New Files

- **`Blue_Lagoon/compose_generator.py`** — Generates `docker-compose.honeynet.yml` programmatically via `yaml.dump()`. Creates isolated Docker bridge networks per hop: `net_entry` (Kali ↔ Pot1), `net_hop1` (Pot1 ↔ Pot2), `net_hop2` (Pot2 ↔ Pot3). Kali can only reach the entry pot. Each pot sits on two networks (inbound + outbound) except the last. DB containers placed on the same network as their pot. IP scheme: `172.{RUNID}.{hop}.{10+N}`.
- **`Blue_Lagoon/credential_chain.py`** — `ChainManifest` and `HopInfo` dataclasses mapping each hop's IP, credentials, and hostname. `build_chain_manifest()` loads profiles and computes per-hop IPs. `inject_next_hop_breadcrumbs()` plants real next-hop credentials into: `/etc/hosts` (hostname mapping), `.bash_history` (SSH commands), `~/.ssh/config` (Host block), `/opt/.env` (connection strings), and `lateral_movement_targets` in lure data.
- **`Cowrie/cowrie-src/src/cowrie/commands/ssh_proxy.py`** — `SSHProxySession` class using paramiko in a background thread for real interactive SSH connections between containers. Opens a PTY shell channel, relays attacker keystrokes to remote stdin and remote stdout to attacker terminal via `reactor.callFromThread()`. Handles auth failure ("Permission denied"), connection refused, and graceful disconnect (returns control to local Cowrie shell).
- **`Purple/session_correlator.py`** — Post-hoc multi-hop session correlation. Reads each hop's Cowrie JSON log, matches sessions by source IP (pot1's outbound IP appearing as src_ip on pot2 = same attacker). Produces `AttackerJourney` objects with: total dwell time, per-hop dwell time, commands per hop, files accessed (breadcrumb tracking), pivot success rate. `print_correlation_report()` for human-readable output.

### Modified Files

- **`config.py`** — Added `honeynet_enabled` (bool, default False), `chain_profiles` (list of profile paths for each hop), `chain_db_enabled` (per-hop database toggle).
- **`main.py`** — Split `main()` into `main_single()` (existing logic) and `main_honeynet()`. New honeynet flow: build chain manifest → enrich lures per hop → inject breadcrumbs → deploy per-hop configs → generate compose → start all containers → run Sangria sessions → post-experiment correlation report. Parameterized `deploy_cowrie_config(hop_index)` to deploy to `cowrie_config_hop{N}/`. Added credential-stable per-hop reconfiguration (keeps SSH passwords unchanged, regenerates profile content + re-injects breadcrumbs, stops/starts individual containers).
- **`Blue_Lagoon/honeypot_tools.py`** — `_compose_files()` returns honeynet compose file when enabled. Added `get_cowrie_log_path(hop_index)` returning per-hop log paths. `get_new_hp_logs()` accepts `hop_index` param with per-hop offset tracking. `clear_hp_logs()` clears all hops when honeynet enabled. `wait_for_cowrie()` parameterized by `service_name`. Added `wait_for_all_cowrie(chain_length)`, `stop_single_hop(hop_index)`, `start_single_hop(hop_index)`.
- **`Cowrie/cowrie-src/src/cowrie/commands/ssh.py`** — `finish()` checks `HONEYNET_MODE` env var; when set, creates `SSHProxySession` and connects via `deferToThread`. On success, proxy takes over I/O. On failure, falls through to `_simulated_login()` (original behavior). `lineReceived()` forwards to proxy when active. Added `handle_CTRL_C` (sends `\x03` to proxy) and `handle_CTRL_D` (disconnects proxy).
- **`Sangria/attacker_prompt.py`** — Target IP switches from `172.{RUNID}.0.3` to `172.{RUNID}.0.10` (pot1's entry-network IP) when `honeynet_enabled`. Credentials come from pot1's profile (organic discovery only).
- **`Sangria/log_extractor.py`** — Reads `cowrie_config_hop1/` log in honeynet mode (pot1 is where Sangria connects; inner pot commands are logged by those pots).
- **`Cowrie/cowrie-src/requirements.txt`** — Added `paramiko>=3.4.0` for outbound SSH proxy connections.

---

## 2026-03-03d — Lure Category Command Realism Fixes

Systematic audit of Cowrie command handling against all lure categories (cloud, containers, CI/CD, supply chain, privilege escalation) revealed that 9+ critical attacker commands had zero LLM context injection, and `curl` to internal lure hosts made real HTTP requests leaking infrastructure info.

### Critical

- **Sandboxed `curl` for internal/private URLs** — `curl` now detects RFC1918 (`10.x`, `172.16-31.x`, `192.168.x`), link-local (`169.254.x.x` — EC2 metadata), loopback, internal-looking hostnames (`.internal`, `.corp`, `.local`, bare hostnames), and `--unix-socket` requests. These are routed to the LLM fallback handler instead of making real HTTP requests via `treq`. Prevents infrastructure leaks when attackers `curl` lure hosts from `/etc/hosts` or the EC2 metadata endpoint. (`Cowrie/.../commands/curl.py`)

### High

- **Cloud CLI context injection (aws/gcloud/az)** — Added `cloud_context` to prequery `_COMMAND_FAMILIES` for `aws`, `gcloud`, `az`. New `_get_cloud_context()` extracts AWS access keys, secret keys, region, S3 buckets, GCP service accounts, and Azure connection strings from profile `file_contents`. New `format_cloud_context()` provides explicit LLM instructions: fake account ID, ARN, realistic bucket listings, EC2 instance data. Commands now get full profile-aware context instead of blind LLM guessing. (`Cowrie/.../shell/prequery.py`)
- **CI/CD tool context injection (gitlab-runner/gh/jenkins-cli)** — Added `cicd_context` with `_get_cicd_context()` that scans `file_contents` for GitLab, Jenkins, and GitHub config patterns, extracting server URLs and token references. `format_cicd_context()` instructs the LLM to never return "command not found" for CI/CD tools. (`Cowrie/.../shell/prequery.py`)
- **Enhanced Docker/container context** — `container_context` formatter now includes fake running container names extracted from docker-compose files, volume mounts (especially `/var/run/docker.sock`), privileged mode flags, and Kubernetes context paths. Provides explicit LLM instructions for `docker exec`, `docker inspect`, `kubectl get`. (`Cowrie/.../shell/prequery.py`)

### Medium

- **Supply chain context injection (npm/yarn/mvn/gradle)** — Added `supply_chain_context` with `_get_supply_chain_context()` that scans for `.npmrc`, `.pypirc`, `pip.conf`, `settings.xml`, `.yarnrc` in `file_contents`, extracting registry URLs and auth tokens. (`Cowrie/.../shell/prequery.py`)
- **Privilege escalation context (getcap)** — Added `privilege_context` with `_get_privilege_context()` that extracts sudo users, docker group members, and provides SUID/capability hints for the LLM to generate realistic `getcap -r /` and `find / -perm -4000` output. (`Cowrie/.../shell/prequery.py`)

### Low

- **Extended `_COMMAND_FAMILIES` registry** — Added `python3`, `nmap`, `rsync` to prequery command-family mapping for better LLM context on miscellaneous attacker reconnaissance commands. (`Cowrie/.../shell/prequery.py`)

---

## 2026-03-03c — AWS Honeypot Consistency + SSH Prompt Fix

Analysis of `logs/dbtest9_2026-03-03T01_44_56/hp_config_1/full_logs/attack_1.json` revealed two issues: the honeypot profile referenced AWS services (S3 backups, access keys in `.env`) but lacked `awscli` in installed packages and `~/.aws/` config files, causing inconsistent LLM fallback responses; and the attacker LLM wasted 4 turns in a loop trying to answer the SSH host key confirmation prompt.

### High

- **Automatic AWS context enrichment in profile converter** — New `_enrich_aws_context()` runs at the start of `deploy_profile()`. Detects AWS references (S3 URIs, `AWS_ACCESS_KEY_ID`, `aws` commands) in `file_contents` and auto-patches the profile: adds `awscli` to `installed_packages`, creates `/root/.aws/` directory tree, populates `credentials` and `config` files from extracted keys. Idempotent — skips if already present. (`Reconfigurator/profile_converter.py`)
- **AWS CLI context in LLM fallback prompt** — New `_extract_aws_context()` extracts access keys, region, and S3 buckets from the profile. `generate_llm_prompt()` now appends an `AWS CLI CONTEXT` section instructing the LLM to simulate realistic `aws` CLI output (s3 ls, sts get-caller-identity, ec2 describe-instances, etc.) consistent with the profile's credentials. (`Reconfigurator/profile_converter.py`)

### Medium

- **SSH host key confirmation instructions in attacker prompt** — Added explicit `SSH host key verification` section: attacker must respond to fingerprint prompt with a tool call containing only `"yes"`, must NOT send the password until seeing `"password:"`, and the correct 3-step sequence (ssh → yes → password) is documented. Prevents the loop observed in dbtest9 where the attacker sent the password to the fingerprint prompt. (`Sangria/attacker_prompt.py`)

### Low

- **Fixed dbtest9 honeypot config** — Manually patched `hp_config_1/honeypot_config.json`: added `awscli` package, `/root/.aws/` directory tree, and `credentials`/`config` file contents matching the keys already in `.env`. (`logs/dbtest9_.../hp_config_1/honeypot_config.json`)

---

## 2026-03-03b — dbtest9 Multiline Command Fix + Pipeline Cleanup

Analysis of `logs/dbtest9_2026-03-03T01_44_56` revealed that 54% of session time (80s/148s) was wasted on three 40-second timeouts caused by multiline commands. Also cleaned up the config pipeline.

### High

- **Multiline command splitting in terminal_io** — `send_terminal_command()` now detects embedded newlines and delegates to `_send_multiline_command()`, which sends each line individually via `sendline()` and waits for continuation prompts (`> `) or final shell prompts between lines. Eliminates 40s timeouts from heredocs, `echo -e` with `\n`, and quote continuations. Added `_continuation_patterns`, `_all_prompt_patterns`, `_recover_from_timeout()` shared helper. (`Sangria/terminal_io.py`)

### Low

- **Config pipeline cleanup** — Removed unused `import os` and `all_text` variable, replaced all `print()` with `logging`, pre-compiled 3 regexes at module level, added null guard for `extract_json()`, simplified retry loop. (`Reconfigurator/new_config_pipeline.py`)

---

## 2026-03-03 — dbtest7 Fix Plan + ssh-keygen Native Handler

Implemented the four fixes from `docs/dbtest7_fix_plan.md` (file persistence, heredoc support, SCP pull mode, sudo pipe propagation) and added a native `ssh-keygen` command after dbtest8 revealed an infinite LLM prompt loop.

### Critical

- **File persistence across SSH sessions** — `HoneyPotRealm` now caches a single `CowrieServer` instance, reused across all SSH sessions. `initFileSystem()` skips if already initialized. Files written via `echo > file` or `scp` now survive SSH reconnects. (`Cowrie/.../shell/realm.py`, `Cowrie/.../shell/server.py`, `Cowrie/.../llm/realm.py`)

### High

- **Multiline shell input (heredocs + quote continuation)** — `HoneyPotShell.lineReceived()` now buffers unclosed quotes (shows `> ` continuation prompt, prepends buffer on next line) and detects `<<` heredoc syntax (buffers lines until delimiter, writes to file or echoes body). (`Cowrie/.../shell/honeypot.py`)
- **Native `ssh-keygen` command** — New handler supporting `-t` (rsa/ed25519/ecdsa/dsa), `-b`, `-f`, `-N`, `-C`, `-q`, `-l`, `-y`. Generates realistic PEM/OpenSSH key content, creates both private and `.pub` files in the virtual FS with real backing files. Honors `-q` (no interactive prompt). Root cause: LLM fallback generated an `Overwrite (y/n)?` prompt that entered an infinite echo loop when the attacker answered `yes`. (`Cowrie/.../commands/ssh_keygen.py` new)

### Medium

- **SCP pull mode (`-f`)** — `scp.py` now handles the `-f` flag (server sending files). Resolves the file in the virtual FS, reads content from honeyfs/realfile, sends SCP protocol header + content + success marker. (`Cowrie/.../commands/scp.py`)
- **Sudo pipe chain propagation** — When `sudo` creates a `PipeProtocol` for the inner command, it now passes the outer pipe's `next_command` so `sudo netstat -tulnp | grep ':80'` correctly filters output. (`Cowrie/.../commands/sudo.py`)

### Low

- **Registered missing commands in `__all__`** — `dpkg`, `su`, and `ssh_keygen` added to `Cowrie/.../commands/__init__.py`. Previously `dpkg` and `su` existed as files but were not auto-discovered by Cowrie's command loader.

---

## 2026-03-01 — Fake Database Honeypot Service

Added an ephemeral database container (MySQL or PostgreSQL) that is profile-matched, auto-seeded with realistic data, and integrated with Cowrie's LLM fallback. One fixed DB version runs internally (`postgres:16` / `mysql:8.0`); the version string is spoofed to the attacker via the LLM layer.

### New Files

- **`Reconfigurator/db_seed_generator.py`** — Extracts DB engine, credentials, and spoofed version from profile JSON. Generates init SQL: WordPress schema (~500 rows) for MySQL, business-app schema (~415 rows) for PostgreSQL. Credential sources: `wp-config.php`, `.env`, `.pgpass`, `pgbouncer/userlist.txt`, shell scripts with `MYSQL_PWD`/`PGPASSWORD`.
- **`Cowrie/cowrie-src/src/cowrie/shell/db_proxy.py`** — `DBProxy` class using `pymysql` (MySQL) and `pg8000` (PostgreSQL), both pure Python. Lazy connection, query execution capped at 100 rows, schema discovery (databases/tables/row counts).

### Modified Files

- **`config.py`** — Added constants: `DB_CONTAINER_IP_SUFFIX`, `DB_MYSQL_IMAGE`, `DB_POSTGRES_IMAGE`, `DB_ROOT_PASSWORD`, `DB_PROXY_TIMEOUT`.
- **`Blue_Lagoon/honeypot_tools.py`** — Added `generate_db_compose()` (writes `docker-compose.override.yml` with `honeypot-db` service, static IP .0.4, healthcheck, Cowrie env vars), `remove_db_compose()`, `wait_for_db()`. Modified `_compose_env()` to inject DB vars from `db_config.json`. Modified `start_dockers()`/`stop_dockers()` to include override file when present.
- **`Reconfigurator/profile_converter.py`** — Added `_extract_db_version()` helper. Modified `generate_llm_prompt()` to append `DATABASE VERSION CONTEXT` block instructing the LLM to always report the spoofed version string.
- **`Cowrie/cowrie-src/src/cowrie/shell/prequery.py`** — Added `format_db_query_result()` (ASCII table of real query results) and `format_db_discovery()` (schema overview for LLM context).
- **`Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py`** — Added `_init_db_proxy()` (reads `COWRIE_DB_*` env vars), `_extract_sql_from_command()` (parses `-e`/`-c` flags for inline SQL). Modified `__init__()`/`reload_profile()` to manage proxy lifecycle. Modified `build_prompt()` to execute real SQL or discovery and inject results into LLM context.
- **`main.py`** — Modified `deploy_cowrie_config()` to run the DB seed pipeline (`extract_db_config` → `generate_init_sql` → `write_db_init_scripts` → `generate_db_compose`). Added `wait_for_db()` after both `wait_for_cowrie()` call sites. Cleans up stale DB files when profile has no database.
- **`Cowrie/cowrie-src/requirements.txt`** — Added `pymysql>=1.1.0`, `pg8000>=1.31.0`.
- **`docs/DESIGN_FAKE_DATABASE.md`** — Added "Version Spoofing Mechanism" section, replaced `psycopg2-binary` with `pg8000`, updated image references to fixed versions.

---

## 2026-02-25b — Honeypot Detection Countermeasures

Analysis of `logs/senaste_2026-02-25T21_50_55` showed both attack sessions detected the honeypot. Six root causes identified; five fixed (Issue 6 — filesystem persistence across SSH sessions — deferred).

### Critical

- **Replaced fake SSH key** — `cowrie_config/honeyfs/home/deploy/.ssh/id_rsa` contained the literal string `fake_key_bytes_for_honeypot_simulation_only`. Replaced with realistic base64 Ed25519 key data. Updated both profile JSONs to match. (`cowrie_config/honeyfs/home/deploy/.ssh/id_rsa`, `Reconfigurator/profiles/wordpress_server.json`, `cowrie_config/etc/profile.json`)
- **Made `netstat` profile-aware** — `netstat -tulnp` only showed SSH port 22 in LISTEN state, contradicting the profile's Apache (80, 443), MySQL (3306), and SSH (22) services. Now reads services from the loaded profile and dynamically generates LISTEN lines for each. Added `-p` flag support showing PID/program names. Falls back to SSH-only if no profile is loaded. (`Cowrie/cowrie-src/src/cowrie/commands/netstat.py`)

### High

- **Fixed `sudo -u user -i` parsing** — `getopt` string defined `-i` as requiring an argument (`i:`), but `sudo -i` is a standalone flag. `sudo -u deploy -i` produced `sudo: illegal option -- i`. Removed colons from `-i` and `-s` to make them boolean flags. Added handling so `-i`/`-s` without a command silently succeeds. (`Cowrie/cowrie-src/src/cowrie/commands/sudo.py`)
- **Implemented `su` command** — `su` was mapped to `Command_nop` (silent no-op). Attackers tried `su - deploy` 4+ times with zero output. New `Command_su` supports `-`/`-l` (login shell), `-c command`, user targeting. As root: silent success with env update. As non-root: password prompt then success. Validates users against profile, respects nologin shells. (`Cowrie/cowrie-src/src/cowrie/commands/su.py` new, `Cowrie/cowrie-src/src/cowrie/commands/base.py`)

### Medium

- **Fixed MySQL credential rejection by LLM** — `mysql` falls through to LLM fallback, which received db service context but not the actual valid credentials. LLM decided credentials were invalid, returning `ERROR 1045 Access denied` despite creds matching `wp-config.php`. Added `extract_db_credentials()` to parse credentials from profile file_contents (wp-config.php, .env, shell scripts) and inject them into LLM context with "authentication MUST succeed" instruction. Also updated LLM system prompt. (`Cowrie/cowrie-src/src/cowrie/shell/prequery.py`, `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py`, `cowrie_config/etc/llm_prompt.txt`)

### Deferred

- **File writes don't persist across SSH sessions** — Cowrie starts each SSH session with a fresh filesystem pickle. Attacker wrote `authorized_keys`, exited, reconnected, and found it gone. Architecturally hard to fix; deferred to future iteration.

---

## 2026-02-25 — Honeypot Realism Fixes

Root cause analysis of session `s_2026-02-25T17_56_37` where both attackers detected the honeypot due to empty command outputs.

### Critical

- **Fixed LLM model name in cowrie.cfg** — `str(LLMModel.GPT_4_1_MINI)` produced `"LLMModel.GPT_4_1_MINI"` instead of `"gpt-4.1-mini"`, causing the OpenAI API to reject every request. All LLM-fallback commands (`mount`, `dpkg -l`, `getent passwd`, `systemctl`, `ssh-keygen`, etc.) silently returned empty output. (`main.py`, `cowrie_config/etc/cowrie.cfg`)

### High

- **Fixed txtcmds path resolution** — `getCommand()` in `protocol.py` only checked the built-in package txtcmds, ignoring the config-specified `txtcmds_path` where profile-generated outputs (`df`, `ps`, `netstat`, `ifconfig`) are written. Now checks the config path first, then falls back to built-in. (`Cowrie/cowrie-src/src/cowrie/shell/protocol.py`)

### Medium

- **Added `/etc/crontab` generation** — `profile_converter.py` now generates `/etc/crontab` from the profile's `crontabs` data. Previously `cat /etc/crontab` returned empty. (`Reconfigurator/profile_converter.py`)
- **Added `printenv` command alias** — `printenv` was not registered as a Cowrie command. Now aliases to the `env` handler. (`Cowrie/cowrie-src/src/cowrie/commands/env.py`)
- **Populated session environment variables** — Added `HOSTNAME`, `LANG`, `LANGUAGE`, `MAIL`, `PWD` to the session environ so `env`/`printenv` output looks realistic. (`Cowrie/cowrie-src/src/cowrie/shell/session.py`)

### Low

- **Documented CommandOutput limitation** — Clarified in `log_extractor.py` that Cowrie's JSON log does not capture command output (terminal output goes directly over SSH, not through the log plugin).
