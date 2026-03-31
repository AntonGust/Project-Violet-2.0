# Project Violet 2.0 — Complete Workflow Explained

## What It Is

Project Violet is a **closed-loop cybersecurity research platform** that autonomously attacks its own honeypots using LLM-powered red teaming, then analyzes the results and adaptively reconfigures the honeypots to elicit more diverse attack behavior. It generates labeled attack datasets mapped to the MITRE ATT&CK framework.

---

## The Five Core Components

| Component | Role |
|-----------|------|
| **Sangria** | LLM-powered autonomous attacker (red team) |
| **Cowrie** | Modified SSH honeypot with LLM fallback for unknown commands |
| **Reconfigurator** | Adaptive profile generation & novelty checking |
| **Blue Lagoon** | Docker orchestration & network infrastructure |
| **Purple** | Post-attack analysis, MITRE labeling, CHeaT defense detection |

---

## End-to-End Workflow

### Phase 1: Profile & Deployment

```
Profile JSON  ──►  Reconfigurator/profile_converter.py  ──►  Cowrie Artifacts
```

A **profile** is a JSON file describing a complete fake Linux server — OS, users, services, installed packages, file contents, network config, and embedded **lures** (breadcrumb credentials, lateral movement targets, privilege escalation paths).

The converter transforms this into 7 Cowrie artifacts:
- **`fs.pickle`** — Virtual filesystem tree (directories, files, symlinks)
- **`honeyfs/`** — Actual file contents (`/etc/passwd`, `/etc/shadow`, configs, logs)
- **`txtcmds/`** — Static command outputs (`ps aux`, `ifconfig`, `df -h`, `uname -a`)
- **`userdb.txt`** — SSH login credentials
- **`llm_prompt.txt`** — System prompt for the honeypot's LLM fallback
- **`profile.json`** — Raw profile for runtime context injection
- **`cowrie.cfg`** — Hostname, kernel, arch overrides

### Phase 2: Infrastructure Spin-Up

Blue Lagoon starts Docker containers:
- **Kali** — Attack staging box (SSH entry point)
- **Cowrie** — The honeypot itself (port 2222)
- **Optional DB** — Real MySQL/PostgreSQL seeded with fake data

For **multi-hop honeynet** mode, 2-3 Cowrie instances are chained across isolated Docker networks with real SSH proxying between them. Credential breadcrumbs are injected into each hop pointing to the next.

### Phase 3: Attack Loop (Sangria)

```
LLM  ──►  Tool Call (terminal_input)  ──►  SSH to Kali  ──►  Cowrie  ──►  Response  ──►  LLM
```

Each session runs an iterative loop:
1. The LLM receives the conversation history and decides what command to run
2. Each command is labeled with a **MITRE tactic + technique** at decision time
3. The command is executed via SSH through Kali into Cowrie
4. Cowrie handles the command through a **three-tier system**:
   - **Tier 1**: Pickle filesystem (directory listings, file metadata)
   - **Tier 2**: HoneyFS (file contents for `cat`, `head`, `tail`)
   - **Tier 3**: TxtCmds (static outputs for system commands)
   - **Tier 4 (fallback)**: LLM generates a response using **pre-query context injection** — only the relevant slice of the profile is sent (not the whole thing), keeping token cost flat regardless of session length
5. The loop repeats until the LLM calls `terminate` or hits the iteration limit

### Phase 4: Session Extraction & Analysis

After each session:
- **Extract** structured data: commands, MITRE labels, tactic transitions, session length
- **CHeaT detection** checks if planted defenses were triggered (unicode honeytokens, canary URLs, prompt traps, tool traps)
- **Token usage** is aggregated for both attacker and honeypot LLMs
- Results are appended to `sessions.json` and a markdown report is generated

### Phase 5: Adaptive Reconfiguration

The Reconfigurator monitors attack patterns and decides when to generate a new profile. Four criteria are available:

| Method | Trigger |
|--------|---------|
| **NO_RECONFIG** | Never — single profile for all sessions |
| **BASIC** | Every N sessions |
| **ENTROPY** | Shannon entropy of tactic distribution plateaus (attacker has converged) |
| **T_TEST** | Sessions become statistically indistinguishable (p-value above confidence threshold) |

When triggered:
1. An LLM generates a **novel** profile (validated against JSON schema + lure requirements)
2. **Jaccard distance** is computed against all prior profiles — must exceed novelty threshold (default 0.4)
3. New artifacts are deployed, Docker restarts, and the cycle continues

### Phase 6: Purple Analysis

Post-experiment analysis includes:
- **HP comparison** — Session lengths across configurations
- **Meta-analysis** — Tactic distributions, deceptiveness metrics
- **Session correlation** (honeynet mode) — Chain multi-hop sessions into "Attacker Journeys" via IP-chain matching
- **Visualizations** — matplotlib charts of MITRE coverage, entropy trends

---

## Multi-Hop Honeynet Architecture

```
Kali (attacker)
  └─ net_entry ─── Hop 1 (e.g., WordPress server)
                      └─ net_hop1 ─── Hop 2 (e.g., Database server)
                                         └─ net_hop2 ─── Hop 3 (e.g., CI/CD runner)
```

- Each hop is an independent Cowrie with its own profile
- Credential breadcrumbs in Hop 1 point to Hop 2's real IP/credentials
- SSH between hops uses **real paramiko connections** (not simulated)
- Reconfiguration is **credential-stable** — when a hop's profile changes, the chain credentials persist so discovered paths still work

---

## CHeaT Defenses (Counter-Honeypot Evasion Techniques)

Four proactive countermeasures against LLM-based attackers:

| Defense | How It Works |
|---------|-------------|
| **Unicode Honeytokens** | Zero-width characters in credentials — LLM copy-paste gets corrupted |
| **Canary URLs** | Fake URLs in files — monitored when the LLM tries to access them |
| **Prompt Traps** | Prompt injection payloads hidden in file contents — triggers LLM refusal |
| **Tool Traps** | Fake CVE outputs in command responses — wastes attacker iterations |

---

## Key Design Decisions

- **Flat token cost**: Pre-query context injection means Cowrie's LLM cost doesn't grow with session length (~1,600-2,100 tokens regardless of whether it's command 10 or command 100)
- **Separate LLM configs**: Attacker (Sangria) and defender (Cowrie) can use different models/providers
- **Local model support**: Ollama, vLLM, LM Studio all supported with `host.docker.internal` bridging for Docker-to-host access
- **16 pre-built profiles** covering WordPress, database, CI/CD, monitoring, Docker Swarm, dev workstations, backup servers, and more
- **297 tests** with unit, integration, and statistical coverage
