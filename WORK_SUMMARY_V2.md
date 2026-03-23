# Project Violet — Work Summary

## 1. Project Overview

Project Violet is an automated cybersecurity research platform that creates a continuous feedback loop between AI-powered attackers and adaptive honeypots. The system generates labeled datasets for defensive cybersecurity research by running autonomous attack sessions against honeypots that evolve their configurations to elicit diverse attacker behavior.

**Technology stack:** Python 3.11+, OpenAI GPT-4.1 family, Docker/Docker Compose, Cowrie (Python/Twisted), BAAI/bge-m3 embeddings, NumPy/SciPy/scikit-learn.

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Experiment Loop (main.py)                    │
│                                                                     │
│   ┌──────────────┐     SSH      ┌──────────────────────────────┐    │
│   │   Sangria     │────────────>│   Cowrie Hybrid Honeypot     │    │
│   │  (Attacker)   │  via Kali   │                              │    │
│   │              │   container  │  Deterministic FS (pickle)   │    │ 
│   │  GPT-4.1     │<────────────│  + LLM Fallback (GPT-4.1)     │    │
│   │  red-team    │   response   │  + Pre-query Context         │    │
│   └──────────────┘              └──────────────────────────────┘    │
│          │                                   │                      │
│          │ session logs                      │ cowrie.json          │
│          ▼                                   ▼                      │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │                  Reconfigurator                         │       │
│   │                                                         │       │
│   │  Criteria Check ──> Profile Generator ──> Profile       │       │
│   │  (entropy/t-test)   (LLM + schema)      Converter       │       │
│   │                                          (JSON → Cowrie)│       │
│   └─────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘

Docker network: 172.{RUNID}.0.0/24
  Kali container:   172.{RUNID}.0.2
  Cowrie container:  172.{RUNID}.0.3
```

## 3. What Was Built

### 3.1 Cowrie Hybrid Backend

Replaced the original Beelzebub honeypot with a forked Cowrie instance augmented with LLM capabilities. Commands are first handled by Cowrie's deterministic filesystem (pickle tree + honeyfs + txtcmds), and only routed to the LLM when no built-in handler matches.

**Key files:**
- `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py` (544 lines) — `LLMFallbackHandler` with `SessionStateRegister` for per-session state tracking (up to 50 entries with LRU eviction), impact scoring (0=read-only to 4=critical), install detection as overlay, and SIGUSR1 hot-reload of profiles.
- `Cowrie/cowrie-src/src/cowrie/shell/honeypot.py` (712 lines) — Modified `HoneyPotShell` to route unknown commands to the LLM fallback when `[hybrid_llm] enabled = true`.
- `Cowrie/cowrie-src/src/cowrie/shell/protocol.py` (426 lines) — Modified to initialize `LLMFallbackHandler` per session.
- `cowrie_image/Dockerfile` (94 lines) — Multi-stage build: debian:bookworm-slim builder + distroless Python runtime.

### 3.2 Pre-query Context Injection

A command-aware system that analyzes each attacker command before it reaches the LLM, extracts relevant context from the server profile, and injects it into the prompt so the LLM produces responses consistent with the honeypot persona.

**Key file:** `Cowrie/cowrie-src/src/cowrie/shell/prequery.py` (635 lines)

**How it works:**
1. Command is tokenized; wrapper prefixes (sudo, nohup, nice, env, time, strace, su, timeout) are stripped
2. Base command is matched against `_COMMAND_FAMILIES` — 25+ command families mapped to context keys
3. Paths are extracted from arguments using 3 tiers: positional args, flag=value pairs, regex fallback
4. Each path is resolved against the live Cowrie filesystem, then the profile JSON, then parent-path walking
5. Context is assembled into a budget-aware string (max 3000 chars)

**Context types:** packages, services, network, database (with credentials), containers, users, crontabs, directory tree, environment, disk info, firewall rules.

### 3.3 Filesystem Profile Generator

LLM-driven pipeline that generates novel server persona profiles for the honeypot, ensuring each new configuration is meaningfully different from previous ones.

**Key file:** `Reconfigurator/new_config_pipeline.py` (272 lines)

- `generate_new_profile()` — Samples up to 5 previous profiles with their session data (observed MITRE tactics/techniques), builds a prompt with the JSON schema and novelty requirements, queries the LLM, validates against the schema, checks novelty via Jaccard distance, retries up to 3 times.
- `Reconfigurator/profile_distance.py` (78 lines) — Multi-dimensional weighted Jaccard distance across 5 dimensions: OS family, service set, lure file paths, non-root users, listening ports.
- `Reconfigurator/RagData/filesystem_profile_schema.json` (229 lines) — Defines: system (os, hostname, kernel, arch, timezone), users, directory_tree, file_contents, services, network, installed_packages, crontabs, ssh_config, description.
- 3 pre-built profiles in `Reconfigurator/profiles/`: `wordpress_server.json`, `cicd_runner.json`, `database_server.json`.

### 3.4 Profile Converter

Converts a filesystem profile JSON into the 7 artifacts Cowrie needs to simulate a server.

**Key file:** `Reconfigurator/profile_converter.py` (941 lines)

| Artifact | Function | Description |
|----------|----------|-------------|
| `share/fs.pickle` | `profile_to_pickle()` | Cowrie pickle tree — ~50 standard Linux dirs + profile entries + auto-generated system files |
| `honeyfs/` | `generate_honeyfs()` | File contents: /etc/passwd, shadow, group (40+ groups), hostname, os-release, hosts, resolv.conf, fstab, sshd_config, motd, sudoers, .bashrc |
| `share/cowrie/txtcmds/` | `generate_txtcmds()` | Static command outputs: uname, hostname, whoami, id, uptime, ps aux, ifconfig, netstat, df, free |
| `etc/userdb.txt` | `generate_userdb()` | SSH credential file (username:uid:password) |
| `etc/llm_prompt.txt` | `generate_llm_prompt()` | System prompt with OS, services, network, users |
| `etc/profile.json` | (copy) | Raw JSON for runtime pre-query use |
| cowrie.cfg overrides | `generate_cowrie_config_overrides()` | hostname, kernel_version, arch, OS |

Full deployment orchestrated by `deploy_profile()`.

### 3.5 Reconfiguration Criteria

Four criteria that decide when to swap the honeypot configuration, plus an abstract base class (`Reconfigurator/criteria/abstract.py`).

| Criterion | File | Logic |
|-----------|------|-------|
| NO_RECONFIG | `criteria/never.py` (11 lines) | Always returns False |
| BASIC | `criteria/basic.py` (16 lines) | Counter-based: reconfigures after N sessions |
| ENTROPY | `criteria/entropy.py` (52 lines) | Shannon entropy of technique/session-length distributions; triggers on entropy plateau |
| T_TEST | `criteria/ttest.py` (69 lines) | Confidence interval on session lengths or tactic edit distances; triggers when sessions converge statistically |

### 3.6 Terminal I/O Fixes

Rewrote the SSH command execution layer to fix critical buffer synchronization issues.

**Key file:** `Sangria/terminal_io.py` (158 lines)
- `_drain_buffer()` — Reads all pending pexpect data before each command send (fixes off-by-one)
- `_strip_command_echo()` — Removes echoed command from output
- `send_terminal_command()` — Rewritten: drain → send → wait for echo → expect prompt → strip
- Added Cowrie-compatible prompt patterns

**Key file:** `Sangria/log_extractor.py` (85 lines)
- Rewritten from Docker log scraping to file-based byte-offset tracking
- `reset_offset()` for container restarts
- Filters to only `cowrie.command.input` events (fixes duplicate event issue)

### 3.7 Docker Orchestration & Log Management

**`docker-compose.yml`** — Two-service setup:
- **kali**: Attacker container with SSH port `30${RUNID}:3022`
- **cowrie**: Honeypot with hybrid LLM env vars, 4 volume mounts (etc, honeyfs, share, var)
- Bridge network `172.${RUNID}.0.0/24` — RUNID (10-99) enables up to 90 parallel experiments

**`Blue_Lagoon/honeypot_tools.py`** (178 lines) — Docker lifecycle: `start_dockers()`, `stop_dockers()`, `wait_for_cowrie()`, `clear_hp_logs()`.

## 4. Key Files

| File | Lines | Description |
|------|-------|-------------|
| `main.py` | 184 | Experiment orchestrator: setup, attack loop, reconfiguration, Docker lifecycle |
| `config.py` | 38 | Experiment configuration: models, reconfig method, session params |
| `Sangria/sangria.py` | 185 | Attack loop: LLM decision making, tool invocation, token tracking |
| `Sangria/terminal_io.py` | 158 | SSH command execution with pexpect buffer management |
| `Sangria/attacker_prompt.py` | 72 | Red-team system prompt generation |
| `Sangria/log_extractor.py` | 85 | Cowrie log reader with byte-offset tracking |
| `Sangria/llm_tools.py` | 139 | Tool schemas (terminal_input with MITRE labels, terminate) |
| `Sangria/extraction.py` | ~183 | Session extraction from logs (honeypot-only and omni modes) |
| `Blue_Lagoon/honeypot_tools.py` | 178 | Docker start/stop, readiness checking, log management |
| `Reconfigurator/new_config_pipeline.py` | 272 | LLM-driven profile generation pipeline |
| `Reconfigurator/profile_converter.py` | 941 | Profile JSON → 7 Cowrie artifacts |
| `Reconfigurator/profile_distance.py` | 78 | Jaccard distance for profile novelty |
| `Reconfigurator/criteria/entropy.py` | 52 | Shannon entropy reconfiguration criterion |
| `Reconfigurator/criteria/ttest.py` | 69 | T-test confidence interval criterion |
| `Utils/meta.py` | 76 | Experiment folder creation, metadata, reconfigurator selection |
| `Cowrie/.../llm_fallback.py` | 544 | LLM fallback handler with session state and impact scoring |
| `Cowrie/.../prequery.py` | 635 | Pre-query context injection system |
| `Cowrie/.../honeypot.py` | 712 | Modified Cowrie shell with hybrid LLM routing |

## 5. Test Coverage

**297 test functions, 634 assertions across 11 test files (3,946 total lines).**

| File | Tests | Asserts | Coverage |
|------|-------|---------|----------|
| `test_llm_fallback.py` | 56 | 84 | LLMFallbackHandler, SessionStateRegister, impact classification, install detection, prompt building, SIGUSR1 reload |
| `test_prequery.py` | 45 | 68 | Context extraction, path extraction, command family matching, wrapper stripping, compound commands, budget limits |
| `test_profile_converter.py` | 39 | 100 | Pickle generation, honeyfs output, txtcmds, userdb, LLM prompt, full deployment |
| `test_new_pipeline.py` | 15 | 28 | Profile generation, sampling, prompt building, finalization, validation, novelty |
| `test_stats_utils.py` | 38 | 117 | Statistical utility functions |
| `test_metrics_entropy.py` | 23 | 44 | Entropy calculation metrics |
| `test_metrics_mitre_distribution.py` | 22 | 52 | MITRE tactic/technique distribution |
| `test_metrics_sequences.py` | 24 | 60 | Tactic sequence analysis, edit distance |
| `test_metrics_session_length.py` | 20 | 50 | Session length statistics |
| `test_utils.py` | 14 | 27 | JSON extraction, config lock utilities |
| `conftest.py` | — | — | Shared fixtures (wordpress_profile, sample sessions) |

## 6. End-to-End Verification

`scripts/integration_test.sh` (253 lines) runs a 6-step end-to-end verification:

1. **Deploy profile** — Deploys `wordpress_server` profile to `cowrie_config/`, verifies 6 artifacts exist (cowrie.cfg, userdb.txt, llm_prompt.txt, profile.json, fs.pickle, honeyfs/)
2. **Build & start containers** — Builds Cowrie Docker image, starts kali + cowrie containers
3. **Wait for readiness** — Polls for "Ready to accept SSH connections" (60s timeout)
4. **Deterministic commands** — Runs SSH commands from Kali: `ls /home` (checks "deploy" user), `cat /etc/passwd` (checks root+deploy), `uname -a` (checks hostname+kernel), `ps aux` (checks PID header)
5. **LLM fallback tests** (if API key set) — `nmap localhost`, `dpkg -l` (profile packages), `systemctl status apache2` (service status), `mysql -u root -e 'show databases;'` (database names)
6. **Pre-query verification** (if API key set) — Verifies Cowrie logs contain pre-query context markers: INSTALLED PACKAGES, RUNNING SERVICES, DATABASE CONTEXT

## 7. Bug Fixes

Seven command-execution and logging issues were identified and fixed:

| # | Issue | Severity | Fix |
|---|-------|----------|-----|
| 1 | Command output off-by-one — `connection.before` captured previous command's output | CRITICAL | Added `_drain_buffer()` before each command send |
| 2 | Password leaks into shell — "123456" echoed into next command's output | HIGH | Buffer drain clears stale password text |
| 3 | Parallel tool calls desync pexpect — multiple sends without buffer draining | HIGH | `parallel_tool_calls=False` in OpenAI call + buffer drain |
| 4 | Stale honeypot logs — `_file_offset` not reset between runs | MEDIUM | Added `log_extractor.reset_offset()` call in main.py |
| 5 | LLM wastes iterations retrying — sees stale output from #1 (~40% waste) | MEDIUM | Fixed by #1 |
| 6 | Cowrie disconnects mid-session — missing timeout config | MEDIUM | Added `interactive_timeout=600`, `idle_timeout=300`, `authentication_timeout=120` |
| 7 | Duplicate honeypot events — both `command.input` and `command.failed` logged | LOW | Filter to only `cowrie.command.input` events |

Additionally, the profile generation pipeline was hardened with JSON schema validation, novelty checking via Jaccard distance, and retry logic (up to 3 attempts) to ensure every generated profile is valid and distinct.

## 8. Session Formatter

Added automatic Markdown report generation after each attack session.

**Key file:** `Sangria/session_formatter.py`

- `format_session_report(logs, session, tokens_used, output_path)` — Produces a human-readable `.md` report alongside each `attack_N.json` log file
- **Summary header:** command count, unique tactics/techniques with frequency counts, honeypot discovery status, token usage
- **Command timeline:** numbered list of all commands executed
- **Interaction log:** each interaction with tactic/technique labels, terminal command, collapsible terminal output (`<details>` for long output), and assistant reasoning
- Integrated into `main.py` attack loop — reports written to `full_logs/attack_N.md`

## 9. Local Model Support

Added support for using local/self-hosted LLMs (Ollama, vLLM, LM Studio) as drop-in replacements for OpenAI across all LLM consumers.

### 9.1 Shared LLM Client Factory

**Key file:** `Utils/llm_client.py`

- `get_client()` — Returns an `openai.OpenAI` client configured for the active provider (OpenAI, Ollama, vLLM, LM Studio, or custom URL)
- `get_hp_client()` — Separate client for the honeypot's LLM backend (may use a different provider/model)
- Provider URL defaults: Ollama (`localhost:11434/v1`), vLLM (`localhost:8000/v1`), LM Studio (`localhost:1234/v1`)
- All providers use the OpenAI-compatible API — no additional dependencies required

### 9.2 Config Changes

**Modified:** `config.py` — Added 6 new fields:

| Field | Default | Description |
|-------|---------|-------------|
| `llm_provider` | `"openai"` | Provider for Sangria + Reconfigurator (`openai`, `ollama`, `vllm`, `lmstudio`, `custom`) |
| `llm_base_url` | `""` | Custom API endpoint (empty = provider default) |
| `llm_api_key` | `""` | API key (empty = `OPENAI_API_KEY` env var) |
| `llm_provider_hp` | `"openai"` | Provider for Cowrie honeypot LLM |
| `llm_base_url_hp` | `""` | Custom API endpoint for honeypot |
| `llm_api_key_hp` | `""` | API key for honeypot |

### 9.3 Consumer Updates

All 3 Python-side LLM consumers were updated to use `get_client()`:

| Consumer | File | Change |
|----------|------|--------|
| Sangria attack loop | `Sangria/sangria.py` | Replaced `openai.OpenAI()` with `get_client()` |
| Terminal simulation | `Sangria/terminal_io.py` | Replaced `openai.OpenAI()` + hardcoded `gpt-4o-mini` with `get_client()` + `config.llm_model_sangria` |
| Profile generator | `Reconfigurator/new_config_pipeline.py` | Replaced `openai.OpenAI(api_key=...)` with `get_client()` |

### 9.4 Docker Networking for Local Models

Cowrie runs inside Docker and cannot reach `localhost` on the host machine. Two changes enable local model access from containers:

- **`docker-compose.yml`** — Added `extra_hosts: ["host.docker.internal:host-gateway"]` to the cowrie service
- **`main.py` (`_write_cowrie_cfg()`)** — Rewrites `localhost`/`127.0.0.1` to `host.docker.internal` in the honeypot's LLM base URL before writing `cowrie.cfg`

Cowrie's `llm_fallback.py` already supported configurable `host` and `path` fields in `[hybrid_llm]` — no Cowrie code changes were needed.

### 9.5 GPU & Model Recommendations

**Key file:** `docs/local_model_recommendations.md`

Since all LLM consumers run sequentially (Sangria → honeypot → Sangria), a single GPU serves everything:

| Setup | Model | Notes |
|-------|-------|-------|
| 1x L4 (24 GB) | Qwen2.5-32B-Instruct (AWQ, 4-bit) | ~18 GB VRAM, good tool calling support |
| 2x L4 (48 GB) | Qwen2.5-72B-Instruct (AWQ, 4-bit) | ~40 GB VRAM, near-GPT-4 quality |
| 4x L4 | Not recommended | Wasteful for sequential workload |

Recommended serving: vLLM with `--enable-auto-tool-choice --tool-call-parser hermes` for function calling support.

## 10. Settings Menu

**Modified:** `main_menu.py` — Complete rewrite with interactive Settings menu.

### Main Menu Structure
```
1. Start New Experiment
2. Settings                  ← NEW
3. Prepare Experiment Data
4. Exit
```

### Settings Submenu
```
1. View Current Settings     — Display all config values
2. Honeypot Profile          — Browse/preview/select profiles from Reconfigurator/profiles/
3. Models & Providers        — Select LLM provider, model, and base URL for each consumer
4. Session Parameters        — Adjust num_sessions, max_session_length, reconfig interval
5. Reconfiguration           — Choose reconfig method (none/basic/entropy/t-test) + threshold
6. Attacker Options          — Toggle simulate_command_line, set experiment name
```

### Key Features
- **Profile browser:** Auto-discovers profiles from `Reconfigurator/profiles/*.json`, displays summaries (hostname, OS, services, users, lure count), allows preview of full JSON
- **Provider selection:** Choose OpenAI/Ollama/vLLM/LM Studio/custom for main consumers and separately for the honeypot Docker container
- **Local model names:** For non-OpenAI providers, accepts free-text model names (e.g., `qwen2.5:32b-instruct`)
- **`apply_partial_config(updates)`:** Writes settings back to `config.py` via regex substitution, supporting string, bool, int, float, LLMModel enum, and ReconfigCriteria fields
