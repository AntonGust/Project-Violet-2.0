# Sangria: Autonomous LLM-Powered Red Team Attacker

## Overview

Sangria is a closed-loop autonomous red team agent that performs SSH-based attacks against honeypots via large language models. It operates as:

1. **LLM Decision** — model receives attack state + conversation history, decides next action
2. **Tool Execution** — model calls `terminal_input` with MITRE ATT&CK labels, or `terminate`
3. **Terminal I/O** — commands execute on Kali Linux via pexpect SSH tunnel
4. **State Tracking** — discoveries (hosts, credentials, files, services) tracked in a structured register
5. **History Management** — state register enables safe trimming of old messages
6. **Session Logging** — full conversation + honeypot events + state saved for analysis

## Core Loop (`sangria.py`)

```
for i in range(max_session_length):
    Rebuild system prompt with current attack state register
    Call LLM with messages, tools, tool_choice="auto"
    Parse response for tool calls
    For each tool call:
        Capture honeypot logs (BEFORE tool execution)
        Execute tool (terminal_input or terminate)
        Update attack state register
        Log to file with honeypot events
        Display to terminal
    [Optional] Follow-up LLM call for narrative reasoning
    Trim message history if window exceeded
    Break if terminate called
```

**Key design decisions:**
- **Parallel tool calls disabled** — rapid-fire execution causes pexpect buffer desynchronization
- **System prompt rebuilt every iteration** — injects current attack state register
- **Honeypot logs captured before tool response** — ensures proper event association
- **Follow-up call is conditional** — OpenAI: without tools (forces text), other providers: with tools (prevents broken JSON), disabled: skip entirely (saves ~47% tokens)

## Prompt Engineering (`attacker_prompt.py`)

### Prompt Structure

Four components combined into the final system prompt:

1. **Base prompt** — role definition, constraints, SSH fingerprint protocol, timeout handling
2. **Target credentials** — IP, port, user/password (if `provide_honeypot_credentials` is enabled)
3. **Objectives** — priority ordering (reconnaissance → exploitation → termination)
4. **Model-specific addendum** — behavioral overrides per LLM family

### Model Family Detection

```python
if "gpt-" or "o4-" or "o3-" in model: → OPENAI
if "llama" in model:                   → LLAMA
if "deepseek" in model:                → DEEPSEEK
if "qwen" in model:                    → QWEN
else:                                  → DEFAULT
```

### Model-Specific Addenda

#### OpenAI
No addendum needed. OpenAI models handle tool calls, strict mode JSON, and multi-turn reasoning reliably.

#### Llama
- NEVER SSH to the same host more than once
- NEVER repeat a command you already ran
- Tool is called `terminal_input` (not `send_command`)
- When sending a password, use `terminal_input` with ONLY the password
- After `ls` or `find`, immediately `cat` interesting files
- Keep a mental checklist: web configs, database creds, SSH keys, mail, backups, bash history, .env

**Why:** Llama struggles with persistent session state, command repetition, and tool name hallucination.

#### DeepSeek
- Always respond with a tool call (no pure reasoning text)
- NEVER repeat the same command twice
- Do not terminate until exhausted every path

**Why:** DeepSeek is reasoning-heavy and may spend tokens on pure reasoning without taking action.

#### Qwen
- Tool is called `terminal_input` with args: `input`, `tactic_used`, `technique_used`
- NEVER SSH to the same host more than once
- After listing files, READ them before moving on

**Why:** Qwen requires strict positional argument names and is sensitive to repetition.

### Thorough Exploitation Checklist

Optional staged discovery workflow (`config.thorough_exploitation_prompt = True`):

1. Search for credential files (`find` for *.conf, *.env, *.key)
2. Read discovered files
3. Check standard locations (/home/\*/.bash_history, /root/.bash_history, /var/backups/\*, /opt/\*/config\*)
4. Connect to databases with found credentials
5. Use SSH keys/passwords for lateral movement
6. Do NOT terminate until all credentials attempted

## Attack State Register (`attack_state.py`)

### Data Model

```
AttackStateRegister
├── hosts: {ip → HostEntry(ip, hostname, access_level, access_method, visited)}
├── credentials: [CredentialEntry(credential, source, cred_type, used, used_where)]
├── files_read: [FileEntry(path, host, summary)]
├── services: [ServiceEntry(host, port, service, accessed)]
├── current_host: str
├── failed_attempts: [str]
```

All categories capped at 50 entries.

### Credential Detection: Regex-Based Extraction

When the attacker reads a file (`cat`, `head`, `tail`, `less`, `more`), the register scans the **command output** (not any internal profile data) using 12 regex patterns:

| Pattern | Type | Example Match |
|---------|------|---------------|
| `password\|passwd\|pwd = ...` | password | `password = mysecret` |
| `AKIA[A-Z0-9]{16}` | aws_key | `AKIAIOSFODNN7EXAMPLE` |
| `api_key\|token\|secret = ...` | api_key | `api_key = abc123` |
| `mysql://user:pass@...` | db_connection | `mysql://root:pass@localhost` |
| `postgres://user:pass@...` | db_connection | `postgres://admin:s3cret@db` |
| `-----BEGIN ... PRIVATE KEY-----` | ssh_key | RSA/OpenSSH private keys |
| `define('DB_PASSWORD', '...')` | db_wp | WordPress wp-config.php |
| `DB_PASSWORD=...\|MYSQL_PASSWORD=...` | db_env | .env file credentials |
| `MYSQL_PWD=...` | db_mysql | Shell script MySQL passwords |
| `PGPASSWORD=...` | db_postgres | Shell script PostgreSQL passwords |
| `sshpass -p '...'` | ssh_password | Bash history SSH passwords |
| `AWS_SECRET_ACCESS_KEY=...` | aws_secret | AWS secret keys |

This approach ensures the attacker agent only "discovers" credentials it has actually seen in terminal output — matching what a real LLM attacker would observe. No profile oracle or internal honeypot data is used.

### Prompt Injection Format

The register is injected into the system prompt each iteration:

```
ATTACK STATE (auto-tracked):

HOSTS:
  172.10.0.3 (wp-prod-01) — root access via SSH port 2222 visited
  172.10.0.5 (backup-srv) — discovered access

CREDENTIALS:
  [USED]   root/123456 (ssh, source: attacker_provided) → SSH 172.10.0.3
  [UNUSED] deploy/d3pl0y! (password, source: /var/mail/deploy)

FILES WITH SECRETS:
  172.10.0.3:/var/www/html/wp-config.php — DB creds: root/dbpass@localhost

SERVICES:
  172.10.0.3:3306 MySQL 5.7 — accessed
  172.10.0.3:80 Apache 2.4.41 — NOT YET ACCESSED

FAILED ATTEMPTS:
  ssh deploy@172.10.0.5 — Connection refused

CURRENT POSITION: root@wp-prod-01
```

Cost: ~300-500 tokens regardless of session depth (vs unbounded growth with raw history).

## Tool Schema (`llm_tools.py`)

### Two Tools

- `terminal_input` — execute a command, label with MITRE ATT&CK tactic/technique
- `terminate` — end the session with a honeypot detection judgment (`success: bool`)

### OpenAI vs. Other Providers

**OpenAI (strict mode):** `tactic_used` and `technique_used` are enum-constrained to the full MITRE ATT&CK taxonomy. `strict: True` and `additionalProperties: False` prevent schema deviation.

**Other providers (free-text):** No enum constraints — fields are described as "MITRE ATT&CK tactic ID and name, e.g. 'TA0007:Discovery'" to give the model flexibility while guiding toward MITRE format. Non-OpenAI models struggle with strict mode and large enums.

### Hallucination Recovery

Three normalization layers handle tool call errors:

1. **Tool name remapping:** `send_command`, `send_password`, `run_command`, `execute`, `ssh_input` all remap to `terminal_input`
2. **Argument key discovery:** If `input` key is missing, use the first non-tactic/technique key (e.g., `command`, `password`, `text`)
3. **Last-resort fallback:** Unknown tool name with input-like arguments is treated as `terminal_input`

## Terminal I/O (`terminal_io.py`)

### Architecture

pexpect-based SSH tunnel to a Kali Linux container at port `3000 + RUNID`.

### Command Execution Protocol

**Phase 1: Buffer Drain** — consume all pending data from previous commands to prevent contamination.

**Phase 2: Command Transmission & Echo Sync** — send command, wait for echo of first 40 characters to confirm receipt.

**Phase 3: Prompt Matching & Output Extraction** — wait for a shell prompt pattern (Kali `#`, honeypot `user@host:~$`, password prompt, SSH fingerprint prompt). Strip command echo from output.

### Special Handling

- **SSH fingerprint prompts** — auto-accepted with "yes"
- **Password prompts** — detected and forwarded (password_mode skips echo sync)
- **Multiline commands** — sent line by line with continuation prompt detection
- **Timeouts (>40s)** — sends Ctrl+C, returns `***COMMAND TOOK TOO LONG TO RUN, KILLING COMMAND***`
- **Long output (>5000 chars)** — truncated to last 5000 characters

## Session Extraction (`extraction.py`)

### Two Modes

**Honeypot-only (`extract_session`):** Filters to commands that actually executed on the honeypot (matched against Cowrie logs). Only includes commands the honeypot saw.

**Omni (`extract_everything_session`):** Includes all commands the LLM requested, regardless of honeypot response — including failed commands, blocked attempts, and commands that returned no output.

### MITRE ATT&CK Labeling

Each tool call's `tactic_used` and `technique_used` fields are extracted and cleaned:
- `"TA0007:Discovery"` → `"Discovery"`
- `"T1018:Remote System Discovery"` → `"Remote System Discovery"`

Labels are counted and deduplicated per session.

### Honeypot Detection

The `terminate` tool's `success` argument indicates whether the LLM judged the target as a honeypot (`True`) or real system (`False`).

## Token Optimization

### Three-Layer Strategy

| Layer | Mechanism | Savings |
|-------|-----------|---------|
| Attack State Register | Compact summary replaces raw history | Bounded at ~500 tokens vs unbounded |
| Sliding Message Window | Keep system prompt + last N iterations | 75-92% at depth 50+ |
| Follow-up Call Toggle | Disable narrative reasoning calls | ~47% of total prompt tokens |
| Output Truncation | Cap command output at 5000 chars | Prevents single-command context blowup |
| OpenAI Prompt Caching | System prompt + tools cached at 10% rate | Automatic for OpenAI models |

### Token Growth Comparison

| Session Depth | Raw History | With Register + Window=10 | Savings |
|---|---|---|---|
| 10 iterations | ~4,200 tokens/call | ~3,500 tokens/call | 17% |
| 50 iterations | ~16,200 tokens/call | ~4,000 tokens/call | 75% |
| 100 iterations | ~31,200 tokens/call | ~4,500 tokens/call | 86% |
| 200 iterations | ~61,200 tokens/call | ~5,000 tokens/call | 92% |

## Anti-Loop Mechanisms

- **Failed attempt tracking** in the state register (visible to the model)
- **Host visited flags** — `visited` marker prevents re-SSHing to the same host
- **Model-specific anti-repetition rules** in prompt addenda
- **Credential used/unused tracking** — model sees which credentials have been tried

There is no automated loop breaker; the system relies on the model understanding the prompt instructions and the state register making past attempts visible.
