# Project Violet 2.0

An automated cybersecurity research platform that creates a continuous feedback loop between AI-powered attackers and adaptive honeypots. Project Violet uses autonomous red team operations, LLM-enhanced honeypots, and adaptive reconfiguration to generate labeled attack datasets for defensive security research.

## Architecture

```
                         ┌──────────────────────────────┐
                         │        main_menu.py           │
                         │   Interactive CLI Interface    │
                         └──────────────┬───────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
   ┌─────────────────┐     ┌────────────────────┐    ┌────────────────────┐
   │    Sangria       │     │   Blue_Lagoon       │    │   Reconfigurator   │
   │  LLM Attacker    │────▶│  Honeypot Infra     │◀───│  Adaptive Profiles │
   │                  │     │  (Cowrie/Docker)     │    │                    │
   └────────┬─────────┘     └────────────────────┘    └────────────────────┘
            │                                                    ▲
            ▼                                                    │
   ┌─────────────────┐                                           │
   │     Purple       │───────────────────────────────────────────┘
   │   Analysis &     │   Attack pattern analysis triggers
   │   MITRE Labels   │   profile reconfiguration
   └──────────────────┘
```

**Core loop:** Deploy honeypot → LLM attacks it → Extract & label sessions → Analyze patterns → Generate new profile → Redeploy

## Prerequisites

- Docker & Docker Compose
- Python 3.11+
- `.env` file in the project root:

```
OPENAI_API_KEY="{your-openai-api-key}"
TOGETHER_AI_SECRET_KEY="{your-togetherai-api-key}"
TOKENIZERS_PARALLELISM=false
```

## Quick Start

```bash
pip install -r requirements.txt
python main_menu.py
```

The interactive menu provides five workflows:

| Option | Description |
|--------|-------------|
| **Start New Experiment** | Configure models, reconfiguration method, session count, then run |
| **Demo Mode** | Showcase honeypot capabilities with scripted SSH sessions |
| **Settings** | Adjust LLM providers, models, profiles, CHeaT defenses |
| **Prepare Experiment Data** | Extract structured sessions from raw attack logs |
| **Run Purple Analysis** | HP comparison, meta analysis, visualizations |

## Components

### Sangria (Attacker)

Autonomous LLM-powered red team agent that conducts SSH-based attacks via a Kali Linux container.

- **Attack loop** (`sangria.py`): LLM decides actions, executes commands via pexpect SSH, tracks state
- **State register** (`attack_state.py`): Tracks discovered hosts, credentials, files, services; deduplicates commands to prevent loops
- **MITRE labeling** (`llm_tools.py`): Each command is labeled with ATT&CK tactics and techniques at execution time
- **Model-specific tuning** (`attacker_prompt.py`): Behavioral overrides per model (Llama, DeepSeek, Qwen, GPT) to handle tool-calling differences

Supported models: GPT-4.1, GPT-4.1-Mini, O4-Mini, Llama 3.3 70B, Qwen 3.5 397B, DeepSeek V3/R1, and local models via Ollama/vLLM/LMStudio.

### Blue_Lagoon (Honeypot Infrastructure)

Docker orchestration layer for Cowrie honeypot deployment.

- **Container lifecycle** (`honeypot_tools.py`): Build, start, stop, health-check containers
- **Compose generation** (`compose_generator.py`): Generates multi-hop honeynet docker-compose files with correct network topology
- **Credential chaining** (`credential_chain.py`): Seeds breadcrumb credentials across hops for realistic lateral movement

### Cowrie (Modified Honeypot)

Fork of the [Beelzebub](https://github.com/mariocandela/beelzebub) honeypot with an LLM fallback system. When a command has no built-in handler, the honeypot calls the configured LLM to generate a realistic response, making the honeypot harder to fingerprint.

### Reconfigurator (Adaptive Profiles)

Dynamically generates new honeypot configurations based on attack patterns.

- **Profile system**: 16 pre-built JSON profiles (WordPress, database, CI/CD, monitoring, etc.) defining filesystem trees, file contents, and services
- **LLM-driven generation** (`new_config_pipeline.py`): Creates new profiles with lure requirements (breadcrumb credentials, lateral movement targets, privilege escalation paths)
- **Novelty measurement** (`profile_distance.py`): Ensures new profiles are sufficiently different from previous ones
- **Lure enrichment** (`lure_agent.py`): Injects deceptive breadcrumbs into bash history, config files, SSH known_hosts
- **Database seeding** (`db_seed_generator.py`): Generates realistic SQL init scripts for MySQL/PostgreSQL

**Reconfiguration triggers:**

| Method | Description |
|--------|-------------|
| `NO_RECONFIG` | Single profile, no adaptation |
| `BASIC` | Reconfigure every N sessions |
| `ENTROPY` | Shannon entropy of tactics over sliding window |
| `T_TEST` | Statistical significance testing on tactic sequences |

### Purple (Analysis)

Post-attack analysis, MITRE ATT&CK labeling, and visualization.

- **HP Comparison** (`hp_comparison_cli.py`): Compare session lengths across experiments
- **Meta Analysis** (`meta_analysis_cli.py`): MITRE tactic distributions, honeypot deceptiveness metrics
- **Visualizations** (`run_analysis.py`): Session length distributions, entropy over time, technique frequency
- **CHeaT detection** (`cheat_detector.py`): Detects attacker defenses against honeypots (unicode honeytokens, canary URLs, prompt injection, tool traps)
- **Session correlation** (`session_correlator.py`): Correlates multi-hop attack sessions

### CHeaT Defenses

Proactive countermeasures against LLM-based attackers:

| Defense | Description |
|---------|-------------|
| Unicode honeytokens | Credentials with zero-width Unicode characters |
| Canary URLs | Honey links planted in files and history |
| Prompt traps | Payloads in file contents to disrupt attacker LLM |
| Tool traps | Fake CVEs and false-positive tool outputs |

## Multi-Hop Honeynet

Project Violet supports multi-hop honeynets where the attacker must discover and pivot between hosts:

```
Kali (attacker)
    ↓ SSH
Hop 1: WordPress Server + MySQL
    ↓ credentials in config files
Hop 2: Database Server + PostgreSQL
    ↓ credentials in CI/CD configs
Hop 3: CI/CD Runner
```

Each hop runs an independent Cowrie instance on a separate Docker network. Credential breadcrumbs and `/etc/hosts` entries guide the attacker to the next hop.

Configure in `config.py`:
```python
honeynet_enabled = True
chain_profiles = [wordpress_server, database_server, cicd_runner]
chain_db_enabled = [True, True, False]
```

## Configuration

All settings are managed through `config.py` (or interactively via the menu):

```python
# LLM providers: openai | togetherai | ollama | vllm | lmstudio | custom
llm_provider = "togetherai"

# Models for each component
llm_model_sangria = LLMModel.QWEN_3_5_397B
llm_model_honeypot = LLMModel.QWEN_3_5_397B
llm_model_reconfig = LLMModel.LLAMA_3_3_70B

# Reconfiguration strategy
reconfig_method = ReconfigCriteria.ENTROPY

# Session parameters
num_of_sessions = 400
max_session_length = 200

# CHeaT defenses
cheat_enabled = True
cheat_unicode_honeytokens = True
cheat_canary_urls = False
cheat_prompt_traps = False
```

## Output Structure

```
logs/
├── {EXPERIMENT_NAME}/
│   ├── metadata.json
│   ├── sessions.json              # Honeypot-visible commands
│   ├── omni_sessions.json         # All attacker commands
│   ├── meta_analysis/
│   │   ├── tactic_distribution.csv
│   │   └── honeypot_deceptiveness.csv
│   ├── analysis_plots/
│   │   ├── session_length_*.png
│   │   ├── mitre_distribution_*.png
│   │   └── entropy_*.png
│   └── hp_config_{N}/
│       ├── honeypot_config.json
│       ├── sessions.json
│       ├── tokens_used.json
│       └── full_logs/
│           └── attack_{N}.json
└── hp_comparison/
    ├── session_length_statistics.csv
    └── session_length_comparison_boxplot.png
```

## Lure Secret Management

Honeypot profiles contain realistic-looking secrets (API keys, tokens) that trigger GitHub push protection. These are managed with a sanitize/restore workflow:

```bash
# Before committing — replace secrets with placeholders
./scripts/restore_lure_secrets.sh --sanitize

# After checkout — restore realistic secrets for deployment
./scripts/restore_lure_secrets.sh
```

Secret mappings are stored in `scripts/.lure_secrets` (gitignored). See the script for details.

## Testing

```bash
# Run all tests
pytest

# Run by category
pytest -m unit
pytest -m integration
pytest -m statistical
```

## Project Structure

```
├── Sangria/              # LLM-powered autonomous attacker
├── Blue_Lagoon/          # Honeypot Docker orchestration
├── Cowrie/               # Modified Beelzebub honeypot with LLM fallback
├── Reconfigurator/       # Adaptive profile generation & lure enrichment
│   └── profiles/         # 16 pre-built honeypot filesystem profiles
├── Purple/               # Analysis, MITRE labeling, CHeaT detection
├── Utils/                # Shared utilities (LLM client, JSON, caching)
├── Tests/                # Unit, integration, and statistical tests
├── scripts/              # Deployment and automation tools
├── docs/                 # Implementation plans and architecture guides
│   ├── done/             # Completed plans
│   ├── doing/            # In-progress work
│   ├── upcoming/         # Planned features
│   └── how-it-works/     # Architecture documentation
├── main_menu.py          # Interactive CLI entry point
├── main.py               # Core orchestration engine
├── demo.py               # Demo mode with scripted attacks
├── config.py             # Centralized configuration
└── docker-compose.yml    # Container definitions
```

## Troubleshooting

**Permission errors with Docker**
- Add your user to the docker group: `sudo usermod -aG docker $USER`
- Log out and back in for changes to take effect

**Lure secrets blocking push**
- Run `./scripts/restore_lure_secrets.sh --sanitize` before committing
- If new secret patterns are added to profiles, add mappings to `scripts/.lure_secrets`

**Cowrie not responding**
- Check container health: `docker ps`
- View logs: `docker-compose logs cowrie`
- Ensure the profile JSON is valid: `python -m Reconfigurator.validate_config <profile.json>`
