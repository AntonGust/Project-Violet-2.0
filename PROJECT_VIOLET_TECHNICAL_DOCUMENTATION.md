# Project Violet: Deep Technical Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Sangria: The AI-Powered Attacker](#sangria-the-ai-powered-attacker)
4. [Beelzebub: The Honeypot System](#beelzebub-the-honeypot-system)
5. [Reconfigurator: Adaptive Honeypot Evolution](#reconfigurator-adaptive-honeypot-evolution)
6. [Data Flow & Session Lifecycle](#data-flow--session-lifecycle)
7. [Configuration System](#configuration-system)
8. [Logging & Metrics](#logging--metrics)
9. [Analysis Pipeline](#analysis-pipeline)

---

## System Overview

Project Violet is an **automated cybersecurity research platform** that creates a continuous feedback loop between AI-powered attackers and adaptive honeypots to generate high-quality labeled datasets for defensive cybersecurity research.

### Core Innovation
- **Autonomous Red Team Operations**: LLM-powered attacker (Sangria) autonomously penetrates targets
- **LLM-Enhanced Honeypots**: Beelzebub honeypot uses LLMs to simulate realistic vulnerable services
- **Adaptive Reconfiguration**: System learns from attack patterns and evolves honeypot configurations
- **Automated Labeling**: All commands are automatically labeled with MITRE ATT&CK tactics and techniques
- **Closed-Loop Research**: Continuous improvement through attack pattern analysis and honeypot adaptation

### Research Goals
1. **Maximize Session Length**: Design configurations that encourage prolonged attacker engagement
2. **Promote Attack Pattern Novelty**: Create diverse and uncommon attack techniques
3. **Generate Realistic Datasets**: Produce authentic attack sequences for defensive AI training
4. **Study Adversarial Adaptation**: Understand how attackers respond to different defensive postures

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Project Violet System                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌───────────────┐         ┌──────────────┐                     │
│  │   Sangria     │  SSH    │  Beelzebub   │                     │
│  │  (Attacker)   │◄────────►│  (Honeypot)  │                     │
│  │               │ Port 30XX│              │                     │
│  └───────┬───────┘         └──────┬───────┘                     │
│          │                         │                              │
│          │ Logs                    │ Logs                         │
│          ▼                         ▼                              │
│  ┌────────────────────────────────────────────┐                 │
│  │         Session Extraction                  │                 │
│  │     (MITRE ATT&CK Labeling)                │                 │
│  └────────────────┬───────────────────────────┘                 │
│                   │                                               │
│                   ▼                                               │
│  ┌────────────────────────────────────────────┐                 │
│  │         Reconfigurator                      │                 │
│  │  - Attack Pattern Analysis                  │                 │
│  │  - Novelty Detection                        │                 │
│  │  - RAG-based Config Generation              │                 │
│  └────────────────┬───────────────────────────┘                 │
│                   │                                               │
│                   │ New Config                                    │
│                   ▼                                               │
│         ┌─────────────────┐                                      │
│         │ Docker Restart  │                                      │
│         └─────────────────┘                                      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Technology Stack
- **Language**: Python 3.11+
- **LLM Providers**: OpenAI (GPT-4.1, GPT-4.1-Mini, O4-Mini, GPT-4.1-Nano)
- **Containerization**: Docker, Docker Compose
- **Honeypot Core**: Beelzebub (Go-based, modified fork)
- **Attacker Environment**: Kali Linux container with SSH
- **Embeddings**: BAAI/bge-m3 (for RAG system)
- **Data Analysis**: NumPy, SciPy, scikit-learn

### Network Architecture

```
Docker Network (172.{RUNID}.0.0/24)
├── Kali Linux Container (172.{RUNID}.0.2)
│   ├── Port 3022 → Mapped to host 30{RUNID}
│   ├── SSH server with credentials (root:toor)
│   └── Full penetration testing toolkit
│
└── Beelzebub Honeypot (172.{RUNID}.0.3)
    ├── Dynamic port configuration (e.g., SSH on 22)
    ├── LLM-powered service simulation
    └── JSON logging output
```

**RUNID**: Unique identifier (10-99) allowing parallel experiment execution

---

## Sangria: The AI-Powered Attacker

Sangria is the autonomous red team component that conducts realistic penetration testing operations against honeypots.

### Architecture Overview

**Location**: [Sangria/](Sangria/)

**Core Files**:
- [sangria.py](Sangria/sangria.py): Main attack orchestration loop
- [terminal_io.py](Sangria/terminal_io.py): SSH connection and command execution
- [llm_tools.py](Sangria/llm_tools.py): Tool definitions and handlers
- [attacker_prompt.py](Sangria/attacker_prompt.py): System prompt generation
- [extraction.py](Sangria/extraction.py): Session data extraction

### Attack Loop Mechanism

#### 1. **Initialization** ([main.py:65-67](main.py#L65-L67))

```python
messages = [
    {'role': 'system', 'content': attacker_prompt.get_prompt(honeypot_config)},
    {"role": "user", "content": "What is your next move?"}
]
```

The system prompt configures the LLM as an autonomous red team operator with:
- SSH access to Kali Linux (172.{RUNID}.0.2)
- Target information (172.{RUNID}.0.3)
- MITRE ATT&CK framework awareness
- Objectives to maximize penetration depth

#### 2. **Main Attack Loop** ([sangria.py:76-169](Sangria/sangria.py#L76-L169))

```python
def run_single_attack(messages, max_session_length, full_logs_path,
                      attack_counter=0, config_counter=0):
```

**Iteration Flow**:

1. **LLM Decision Making** (Line 99)
   - Send conversation history to LLM
   - LLM decides next action via function calling
   - Tracks token usage (prompt, completion, cached)

2. **Tool Invocation** (Lines 122-155)
   - LLM calls `terminal_input` with command and MITRE labels
   - Command executed on Kali Linux via SSH
   - Response captured from honeypot
   - Beelzebub logs extracted and appended to tool response

3. **Follow-up Reasoning** (Lines 157-165)
   - LLM analyzes command output
   - Plans next move based on results
   - Updates internal state

4. **Termination Conditions**
   - Max iterations reached
   - LLM calls `terminate` tool
   - LLM refuses to cooperate

#### 3. **SSH Command Execution** ([terminal_io.py:36-141](Sangria/terminal_io.py#L36-L141))

**Command Execution Flow**:
1. Send command via SSH
2. Wait for terminal prompt pattern
3. Capture response from buffer

**Prompt Patterns**: Multiple terminal prompt formats recognized to handle various system responses.

### Tool System

#### Tool Schema ([llm_tools.py:17-63](Sangria/llm_tools.py#L17-L63))

**terminal_input Tool**:
```json
{
  "name": "terminal_input",
  "parameters": {
    "input": "Command to execute",
    "tactic_used": "MITRE ATT&CK Tactic (e.g., TA0007:Discovery)",
    "technique_used": "MITRE ATT&CK Technique (e.g., T1018:Remote System Discovery)"
  }
}
```

**Auto-Labeling**: LLM must label every command with MITRE ATT&CK categories, enabling automatic dataset annotation.

**terminate Tool**:
```json
{
  "name": "terminate",
  "parameters": {
    "success": "Boolean - true if honeypot discovered"
  }
}
```

### Attacker Prompt Engineering

**System Prompt Features** ([attacker_prompt.py:21-72](Sangria/attacker_prompt.py#L21-L72)):

1. **Role Definition**: "Autonomous red-team operator"
2. **Environment Context**: Full Kali Linux access, target IP
3. **Objectives**: Penetration, persistence, privilege escalation, lateral movement
4. **Constraints**:
   - Single command execution (no chaining)
   - Timeout warnings (>60s)
   - Output size limits (>10KB)
5. **Optional Credential Provision** ([config.py:17](config.py#L17)):
   - Can provide target credentials to skip reconnaissance
   - Controlled via `provide_honeypot_credentials` flag

### Logging & Token Tracking

**Full Conversation Log** ([sangria.py:171-172](Sangria/sangria.py#L171-L172)):
- Every message serialized to JSON
- Includes tool calls, responses, honeypot logs
- Saved to `logs/{experiment}/hp_config_{N}/full_logs/attack_{N}.json`

**Token Usage** ([sangria.py:82-103](Sangria/sangria.py#L82-L103)):
```python
total_tokens_used = {
    "prompt_tokens": total_prompt_tokens,
    "completion_tokens": total_completion_tokens,
    "cached_tokens": total_cached_tokens  # OpenAI prompt caching
}
```

---

## Beelzebub: The Honeypot System

Beelzebub is the adaptive honeypot that simulates vulnerable services and logs attacker interactions.

### What is Beelzebub?

**Original Project**: [mariocandela/beelzebub](https://github.com/mariocandela/beelzebub)
**Language**: Go
**Location**: [Blue_Lagoon/](Blue_Lagoon/)

**Key Modification**: Integration of LLM-powered service plugins for realistic interaction simulation.

### Architecture

#### Core Components

1. **Go Application** ([Blue_Lagoon/main.go](Blue_Lagoon/main.go))
   - Reads configuration from YAML files
   - Spawns service listeners (SSH, HTTP, etc.)
   - Logs interactions as JSON
   - Runs in Docker container

2. **Configuration System**
   - **Core Config**: [Blue_Lagoon/configurations/beelzebub.yaml](Blue_Lagoon/configurations/beelzebub.yaml)
   - **Service Configs**: Dynamic YAML files in [Blue_Lagoon/configurations/services/](Blue_Lagoon/configurations/services/)
   - Generated by Reconfigurator and written as separate service files

3. **Docker Infrastructure** ([docker-compose.yml](docker-compose.yml))

```yaml
services:
  blue_lagoon:
    build: Blue_Lagoon
    environment:
      OPEN_AI_SECRET_KEY: ${OPENAI_API_KEY}
      TOGETHER_AI_SECRET_KEY: ${TOGETHER_AI_SECRET_KEY}
      HP_MODEL: ${HP_MODEL}  # Set from config.py
    volumes:
      - "./Blue_Lagoon/configurations:/configurations"
    networks:
      innet:
        ipv4_address: "172.${RUNID}.0.3"
```

### Service Simulation

#### Configuration Schema

Each service defined in honeypot config has:

```json
{
  "protocol": "ssh",
  "address": ":22",
  "description": "SSH service with CVE-2021-41617",
  "commands": ["whoami", "ls", "cat /etc/passwd"],
  "responses": ["root", "file1.txt file2.txt", "root:x:0:0:..."],
  "banner": "OpenSSH_8.2p1 Ubuntu",
  "cve": "CVE-2021-41617",
  "cve_description": "OpenSSH privilege escalation vulnerability",
  "cve_tags": ["privilege-escalation", "authentication"],
  "plugin": {
    "name": "llm",
    "config": {
      "model": "gpt-4.1-mini",
      "provider": "openai"
    }
  }
}
```

#### LLM Plugin

When `plugin.name = "llm"`:
- Beelzebub intercepts attacker commands
- Sends command + context to LLM
- LLM generates realistic vulnerable service response
- Response returned to attacker
- Entire interaction logged

**This creates highly realistic, contextually aware honeypot services that adapt to attacker behavior.**

### Log Extraction

#### Log Format

Beelzebub outputs JSON logs via Docker logs:

```json
{
  "time": "2025-12-02T10:15:30Z",
  "level": "info",
  "event": {
    "Protocol": "ssh",
    "Command": "ls -la /root",
    "Response": "total 48\ndrwxr-xr-x 5 root root 4096...",
    "SourceIP": "172.10.0.2"
  }
}
```

#### Extraction Mechanism ([log_extractor.py:8-42](Sangria/log_extractor.py#L8-L42))

```python
def get_new_hp_logs():
    # Fetch logs since last check using docker logs --since
    process = subprocess.Popen(
        ["docker", "logs", f"{os.getenv('RUNID')}-blue_lagoon-1",
         "--since", last_checked],
        stdout=subprocess.PIPE
    )
```

**Integration**:
- Called in [sangria.py:129](Sangria/sangria.py#L129) BEFORE creating tool response
- Appended to tool_response as `honeypot_logs` field (Line 142)
- Provides LLM visibility into what honeypot actually received

### Docker Management

#### Container Lifecycle ([Blue_Lagoon/honeypot_tools.py](Blue_Lagoon/honeypot_tools.py))

**Start Containers**:
```python
def start_dockers():
    # Build images with current config
    subprocess.run(["docker", "compose", "-p", runid, "build"])
    # Start containers
    subprocess.run(["docker", "compose", "-p", runid, "up", "-d"])
```

**Stop Containers**:
```python
def stop_dockers():
    subprocess.run(["docker", "compose", "-p", runid, "down"])
    subprocess.run(["docker", "image", "prune", "-f"])
```

**Called during reconfiguration** ([main.py:84, 103](main.py#L84)):
1. Stop containers
2. Generate new config
3. Write new service YAML files
4. Restart containers with new config

---

## Reconfigurator: Adaptive Honeypot Evolution

The Reconfigurator analyzes attack patterns and generates novel honeypot configurations to maintain attacker engagement and diversity.

### Overview

**Location**: [Reconfigurator/](Reconfigurator/)

**Purpose**:
- Detect when current honeypot configuration becomes "stale"
- Generate new configurations that explore different attack surfaces
- Maximize diversity and session length

### Reconfiguration Criteria

Four strategies available, selected in [config.py:11](config.py#L11):

#### 1. NO_RECONFIG ([criteria/never.py](Reconfigurator/criteria/never.py))
- Never reconfigure
- Use same honeypot for all sessions
- Baseline for comparison

#### 2. BASIC ([criteria/basic.py](Reconfigurator/criteria/basic.py))

**Mechanism**: Simple interval-based reconfiguration

```python
def should_reconfigure(self):
    return self.num_sessions >= self.interval
```

**Configuration**: `ba_interval: int = 100` ([config.py:25](config.py#L25))

**Use Case**: Regular reconfiguration regardless of attack patterns

#### 3. ENTROPY ([criteria/entropy.py](Reconfigurator/criteria/entropy.py))

**Mechanism**: Monitors entropy of attack techniques

```python
def compute_entropy(prob_dist):
    return -sum(p * math.log(p) for p in prob_dist if p > 0)

def should_reconfigure(self):
    # Reconfigure when entropy plateaus (change < tolerance)
    smoothed_entropies = moving_average(self.entropies, window_size)
    return abs(smoothed_entropies[-1] - smoothed_entropies[-2]) < tolerance
```

**Configuration** ([config.py:28-30](config.py#L28-L30)):
- `en_variable`: "techniques" or "session_length"
- `en_window_size`: Smoothing window for moving average
- `en_tolerance`: Threshold for detecting plateau

**Rationale**: When attack diversity stops increasing (entropy plateaus), honeypot is no longer eliciting novel behavior → reconfigure.

#### 4. T_TEST ([criteria/ttest.py](Reconfigurator/criteria/ttest.py))

**Mechanism**: Statistical confidence interval analysis

```python
def should_reconfigure(self):
    # Reconfigure when margin of error < tolerance * std
    return self.moes[-1] < self.eps[-1]
```

**Variables**:
1. **session_length**: Monitors consistency of session lengths
2. **tactic_sequences**: Analyzes edit distance between MITRE tactic sequences

**Configuration** ([config.py:33-35](config.py#L33-L35)):
- `tt_variable`: "session_length" or "tactic_sequences"
- `tt_tolerance`: 0.003 for tactics, 0.008 for session_length
- `tt_confidence`: 0.95 (95% confidence level)

**Rationale**: When sessions become statistically similar (narrow confidence interval), attacker behavior has converged → reconfigure to introduce novelty.

### Configuration Generation Pipeline

**Main Function**: [new_config_pipeline.py:262-325](Reconfigurator/new_config_pipeline.py#L262-L325)

#### Step 1: Sample Previous Configurations

```python
def sample_previous_configs(config_dir, sample_size=5):
    # Randomly sample up to 5 previous honeypot configs
    # Extract config JSON and associated session data
```

**Purpose**: Understand what has already been explored to avoid repetition.

#### Step 2: Generate RAG Query via LLM

```python
def build_llm_prompt(sampled_configs):
    """Build prompt instructing LLM to generate RAG query for NEW vulnerabilities"""
    prompt = """
    Generate a user query that will retrieve 5 new and diverse vulnerabilities.
    Your query should explore *new attack surfaces*, *unrelated services*,
    and *alternative TTPs* not already represented.
    DO NOT reference prior services, CVEs, or techniques.
    """
```

**LLM Output Example**: "IoT device firmware vulnerabilities with remote code execution in embedded systems using buffer overflow techniques"

#### Step 3: RAG Retrieval ([new_config_pipeline.py:164-185](Reconfigurator/new_config_pipeline.py#L164-L185))

**Database**: [Reconfigurator/RagData/vulnsDB_cleaned.json](Reconfigurator/RagData/vulnsDB_cleaned.json)
- Cleaned vulnerability data from NVD
- Pre-computed embeddings using BAAI/bge-m3

**Retrieval**:
```python
def retrieve_top_vulns(user_query, vulns_db, embeddings_path, top_n=5):
    model = SentenceTransformer("BAAI/bge-m3")
    query_embedding = model.encode([user_query])[0]
    similarities = [cosine_similarity(query_embedding, emb)
                   for emb in vulns_embeddings]
    top_idx = np.argsort(similarities)[-top_n:][::-1]
    return top_vulns
```

**Output**: 5 CVEs with descriptions semantically similar to the query.

#### Step 4: Generate Configuration via LLM

**Prompt Construction** ([new_config_pipeline.py:187-219](Reconfigurator/new_config_pipeline.py#L187-L219)):

```python
config_prompt = """
You are generating a Beelzebub honeypot configuration.

Strategic Goals:
- Maximize Session Length
- Promote Attack Pattern Novelty

Requirements:
1. Use 1 service with SSH protocol
2. Each service must include a unique CVE
3. All services should use LLM plugin
4. Follow the JSON schema exactly

Schema: {...}

Vulnerabilities:
- CVE-2021-XXXXX: Description...
- CVE-2022-YYYYY: Description...
"""
```

**LLM Output**: Complete honeypot configuration JSON.

#### Step 5: Validation & Novelty Check

**Schema Validation** ([new_config_pipeline.py:233-245](Reconfigurator/new_config_pipeline.py#L233-L245)):
```python
def validate_config(config, schema_path):
    jsonschema.validate(instance=config, schema=schema)
```

**Novelty Check** ([attack_pattern_check.py](Reconfigurator/attack_pattern_check.py)):
```python
def attack_methods_checker(config, experiment_base_path):
    # Compare new config against previous configs using embeddings
    # Reject if too similar (cosine similarity > threshold)
```

**Retry Logic**: Up to 3 attempts to generate valid, novel configuration.

#### Step 6: Deploy Configuration

**Set Honeypot Config** ([new_config_pipeline.py:56-79](Reconfigurator/new_config_pipeline.py#L56-L79)):

```python
def set_honeypot_config(config):
    target_dir = "Blue_Lagoon/configurations/services"
    # Clear old service files
    for file in target_dir.iterdir():
        file.unlink()

    # Write each service as separate YAML file
    for service in config['services']:
        filename = f"service_{service['protocol']}_{config_id}.yaml"
        yaml.dump(service, open(target_dir / filename, "w"))
```

**Lock Mechanism** ([main.py:31, 88](main.py#L31)):
- Uses file lock to prevent Docker from reading partial configs
- Ensures atomic configuration updates

---

## Data Flow & Session Lifecycle

### Complete Experiment Flow

#### 1. Experiment Initialization ([main.py:24-48](main.py#L24-L48))

```python
def main():
    # Create experiment folder: logs/{experiment_name}/
    base_path = create_experiment_folder(config.experiment_name)

    # Load initial honeypot config
    honeypot_config = get_honeypot_config(id=config.llm_provider_hp)

    # Initialize reconfigurator based on selected criteria
    reconfigurator = select_reconfigurator()

    # Start Docker containers
    start_dockers()
```

#### 2. Attack Session Loop ([main.py:57-79](main.py#L57-L79))

```python
for i in range(config.num_of_sessions):
    # Generate attack session
    messages = [system_prompt, initial_user_message]
    logs, tokens_used = run_single_attack(
        messages,
        config.max_session_length,
        logs_path
    )

    # Extract structured session data
    session = extract_session(logs)

    # Update reconfigurator with new session
    reconfigurator.update(session)

    # Save session and token data
    append_json_to_file(session, config_path / "sessions.json")
    append_json_to_file(tokens_used, config_path / "tokens_used.json")
```

#### 3. Reconfiguration Decision ([main.py:80-106](main.py#L80-L106))

```python
    if reconfigurator.should_reconfigure() and not_last_session:
        # Stop honeypot containers
        stop_dockers()

        # Generate new configuration
        honeypot_config = generate_new_honeypot_config(base_path)

        # Acquire config lock
        lock_file = acquire_config_lock()

        # Write new service YAML files
        set_honeypot_config(honeypot_config)

        # Reset reconfigurator state
        reconfigurator.reset()

        # Increment config counter, reset session counter
        config_counter += 1
        config_attack_counter = 0

        # Restart containers with new config
        start_dockers()

        # Release config lock
        release_config_lock(lock_file)
```

### Session Data Structure

#### Full Attack Log ([sangria.py:171](Sangria/sangria.py#L171))

**Saved to**: `logs/{experiment}/hp_config_{N}/full_logs/attack_{N}.json`

```json
[
  {
    "role": "system",
    "content": "You are an autonomous red-team operator..."
  },
  {
    "role": "user",
    "content": "What is your next move?"
  },
  {
    "role": "assistant",
    "content": null,
    "tool_calls": [
      {
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "terminal_input",
          "arguments": {
            "input": "nmap -sV 172.10.0.3",
            "tactic_used": "TA0007:Discovery",
            "technique_used": "T1046:Network Service Discovery"
          }
        }
      }
    ]
  },
  {
    "role": "tool",
    "name": "terminal_input",
    "tool_call_id": "call_abc123",
    "content": "Starting Nmap 7.94...",
    "honeypot_logs": [
      {
        "time": "2025-12-02T10:15:30Z",
        "event": {
          "Protocol": "ssh",
          "Command": "nmap -sV 172.10.0.3",
          "SourceIP": "172.10.0.2"
        }
      }
    ]
  },
  {
    "role": "assistant",
    "content": "The nmap scan reveals port 22 is open..."
  }
]
```

#### Extracted Session ([extraction.py:15-105](Sangria/extraction.py#L15-L105))

**Saved to**: `logs/{experiment}/hp_config_{N}/sessions.json`

```json
{
  "session": "nmap -sV 172.10.0.3 ssh root@172.10.0.3 whoami ls -la cat /etc/shadow",
  "discovered_honeypot": "no",
  "tactics": ["Discovery", "Initial Access", "Collection", "Credential Access"],
  "techniques": ["Network Service Discovery", "Valid Accounts", "Data from Local System", "OS Credential Dumping"],
  "length": 7,
  "full_session": [
    {
      "command": "nmap -sV 172.10.0.3",
      "tactic_raw": "TA0007:Discovery",
      "tactic": "Discovery",
      "technique_raw": "T1046:Network Service Discovery",
      "technique": "Network Service Discovery",
      "content": "The nmap scan reveals port 22 is open..."
    }
  ]
}
```

**Key Difference**:
- **Full logs**: Complete LLM conversation (all tool calls, responses, reasoning)
- **Extracted session**: Only commands that reached honeypot, with MITRE labels

#### Omni Session ([extraction.py:107-183](Sangria/extraction.py#L107-L183))

**Extraction Mode**: `extract_everything_session()`

**Difference**: Captures ALL commands issued by attacker, including:
- Reconnaissance on Kali itself
- Commands that don't reach honeypot
- Failed connection attempts

**Use Case**: Comprehensive attacker behavior analysis including pre-penetration phase.

---

## Configuration System

### Main Configuration File ([config.py](config.py))

```python
from Sangria.model import LLMModel, ReconfigCriteria

# Experiment metadata
experiment_name = "8"  # Or "" for auto-timestamp
run_id = "10"  # 10-99 for parallel experiments

# Model selection
llm_model_sangria = LLMModel.GPT_4_1_MINI
llm_model_blue_lagoon = LLMModel.GPT_4_1_MINI
llm_model_reconfig = LLMModel.GPT_4_1_MINI
llm_provider_hp = "openai"  # openai / togetherai / static

# Reconfiguration strategy
reconfig_method = ReconfigCriteria.BASIC  # NO_RECONFIG / BASIC / ENTROPY / T_TEST

# Testing modes
simulate_command_line = False  # True = use LLM instead of real SSH
provide_honeypot_credentials = True  # True = skip reconnaissance

# Session parameters
num_of_sessions = 400
max_session_length = 120  # Max LLM iterations per session

# Reconfiguration parameters
ba_interval = 100  # BASIC: sessions per config
en_variable = "techniques"  # ENTROPY: what to measure
en_window_size = 1  # ENTROPY: smoothing window
en_tolerance = 1e-2  # ENTROPY: plateau threshold
tt_variable = "tactic_sequences"  # T_TEST: what to measure
tt_tolerance = 0.003  # T_TEST: convergence threshold
tt_confidence = 0.95  # T_TEST: confidence level
```

### Environment Variables ([.env](.env))

```bash
OPENAI_API_KEY="{your-openai-api-key}"
TOGETHER_AI_SECRET_KEY="{your-togetherai-api-key}"
TOKENIZERS_PARALLELISM=false
```

**Loaded in**: [main.py:1-7](main.py#L1-L7)

### Interactive Configuration ([main_menu.py](main_menu.py))

User-friendly interface for setting up experiments:

1. **Experiment Name & Run ID**
2. **Model Selection** (Sangria, Blue Lagoon, Reconfigurator)
3. **Reconfiguration Method** with parameter prompts
4. **Session Parameters** (count, max length)
5. **Additional Options** (simulation mode, credential provision)

**Writes to**: [config.py](config.py) (overwrites existing)

---

## Logging & Metrics

### Log Directory Structure

```
logs/
└── {experiment_name}/                    # e.g., "8" or "experiment_2025-12-02T10-15-30"
    ├── metadata.json                     # Experiment metadata
    ├── sessions.json                     # Combined sessions (all configs)
    ├── omni_sessions.json                # Combined omni sessions
    │
    ├── hp_config_1/                      # First honeypot configuration
    │   ├── honeypot_config.json          # Service configuration used
    │   ├── sessions.json                 # Extracted sessions for this config
    │   ├── omni_sessions.json            # Omni sessions for this config
    │   ├── tokens_used.json              # Token usage per session
    │   └── full_logs/
    │       ├── attack_1.json             # Complete conversation log
    │       ├── attack_2.json
    │       └── ...
    │
    ├── hp_config_2/                      # After reconfiguration
    │   └── ...
    │
    └── hp_config_N/
        └── ...
```

### Metadata ([Utils/meta.py](Utils/meta.py))

**Generated at**: Experiment start
**Location**: `logs/{experiment}/metadata.json`

```json
{
  "experiment_name": "8",
  "timestamp": "2025-12-02T10:15:30",
  "config": {
    "llm_model_sangria": "gpt-4.1-mini",
    "llm_model_blue_lagoon": "gpt-4.1-mini",
    "llm_model_reconfig": "gpt-4.1-mini",
    "reconfig_method": "basic",
    "num_of_sessions": 400,
    "max_session_length": 120
  }
}
```

### Token Usage Tracking

**Tracked per session** ([sangria.py:182-187](Sangria/sangria.py#L182-L187)):

```json
{
  "prompt_tokens": 1250,
  "completion_tokens": 450,
  "cached_tokens": 800  // OpenAI prompt caching savings
}
```

**Saved to**: `logs/{experiment}/hp_config_{N}/tokens_used.json` (one entry per attack)

---

## Analysis Pipeline

### Data Preparation

#### Session Extraction ([Sangria/extraction.py](Sangria/extraction.py))

**Purpose**: Convert raw LLM conversation logs into structured session data.

**Two Modes**:

1. **Honeypot-Only** (`extract_session`):
   - Only commands that reached honeypot
   - Extracted from `honeypot_logs` field in tool responses

2. **Omni** (`extract_everything_session`):
   - All commands issued by attacker
   - Extracted from LLM tool call arguments

**Usage via CLI**:
```bash
python main_menu.py
> Prepare Experiment Data
> Select mode: Honeypot-only / Omni
> Select experiments to process
```

**Scripts**:
- [Scripts/extract_all_logs.py](Scripts/extract_all_logs.py): Batch extraction for single experiment
- [Scripts/combine_sessions.py](Scripts/combine_sessions.py): Merge sessions across configs

#### Combined Sessions

**Generated by**: Preparation pipeline
**Location**: `logs/{experiment}/sessions.json` and `omni_sessions.json`

**Format**: Array of session objects from all configurations.

### Analysis Tools (Purple Component)

**Location**: [Purple/Data_analysis/](Purple/Data_analysis/)

#### 1. HP Comparison ([hp_comparison_cli.py](Purple/Data_analysis/hp_comparison_cli.py))

**Purpose**: Compare session statistics across multiple experiments.

**Outputs** (in `logs/hp_comparison/`):
- `session_length_statistics.csv`: Mean, median, std dev per experiment
- `session_length_comparison_boxplot.png`: Visual comparison
- `session_length_mean_comparison.png`: Bar chart of means

**Metrics**:
- Session length distribution
- Attack success rate
- Honeypot detection rate

#### 2. Meta Analysis ([meta_analysis_cli.py](Purple/Data_analysis/meta_analysis_cli.py))

**Purpose**: Deep dive into single experiment's attack patterns.

**Outputs** (in `logs/{experiment}/meta_analysis/`):
- `tactic_distribution.csv`: MITRE tactic frequency
- `tactic_distribution_*.png`: Visualization
- `honeypot_deceptiveness.csv`: Detection analysis

**Metrics**:
- MITRE tactic/technique distributions
- Unique attack patterns per config
- Session length evolution over time

#### 3. Advanced Visualizations ([run_analysis.py](Purple/Data_analysis/run_analysis.py))

**Interactive plotting system** with modules:

- **Session Length** ([plots/session_length.py](Purple/Data_analysis/plots/session_length.py))
  - Length distribution over time
  - Per-configuration comparison

- **Entropy** ([plots/entropy.py](Purple/Data_analysis/plots/entropy.py))
  - Technique entropy evolution
  - Reconfiguration trigger visualization

- **MITRE Distribution** ([plots/mitre_data.py](Purple/Data_analysis/plots/mitre_data.py))
  - Tactic heatmaps
  - Technique frequency analysis

**Outputs**: `logs/{experiment}/analysis_plots/`

### Statistical Metrics ([Purple/Data_analysis/metrics/](Purple/Data_analysis/metrics/))

#### Entropy Calculation ([metrics/entropy.py](Purple/Data_analysis/metrics/entropy.py))

```python
def calculate_entropy(sessions):
    # Shannon entropy of technique distribution
    technique_counts = Counter(technique for session in sessions
                               for technique in session['techniques'])
    probabilities = [count/total for count in technique_counts.values()]
    return -sum(p * log(p) for p in probabilities)
```

#### Session Length Statistics ([metrics/session_length.py](Purple/Data_analysis/metrics/session_length.py))

```python
def measure_session_lengths(sessions):
    lengths = [session['length'] for session in sessions]
    return {
        'mean': np.mean(lengths),
        'median': np.median(lengths),
        'std': np.std(lengths),
        'min': min(lengths),
        'max': max(lengths)
    }
```

#### MITRE Distribution ([metrics/mitre_distribution.py](Purple/Data_analysis/metrics/mitre_distribution.py))

```python
def measure_mitre_distribution(sessions):
    tactic_counts = Counter()
    technique_counts = Counter()
    for session in sessions:
        tactic_counts.update(session['tactics'])
        technique_counts.update(session['techniques'])
    return {
        'tactics': dict(tactic_counts),
        'techniques': dict(technique_counts)
    }
```

#### Sequence Analysis ([metrics/sequences.py](Purple/Data_analysis/metrics/sequences.py))

```python
def measure_tactic_sequences(sessions):
    # Analyze MITRE tactic sequences using edit distance
    sequences = [session['tactics'] for session in sessions]
    pairwise_distances = []
    for i, seq_i in enumerate(sequences):
        for j in range(i):
            dist = editdistance.eval(seq_i, sequences[j])
            pairwise_distances.append(dist)
    return {
        'sequences': sequences,
        'avg_distance': np.mean(pairwise_distances),
        'diversity_score': len(set(map(tuple, sequences))) / len(sequences)
    }
```

---

## Advanced Features

### Parallel Experiments

**Run ID System** ([config.py:4](config.py#L4)):
- `run_id = "10"` to `"99"` (90 parallel experiments possible)
- Each uses unique Docker network: `172.{RUNID}.0.0/24`
- Each uses unique SSH port: `30{RUNID}`

**Setup**:
1. Copy project directory for each experiment
2. Set unique `run_id` in each copy's [config.py](config.py)
3. Run [main.py](main.py) in each directory

### Simulation Mode

**Testing without Docker** ([config.py:14](config.py#L14)):

```python
simulate_command_line = True
```

**Effect**:
- LLM simulates terminal responses instead of using real SSH
- No Docker containers started
- Faster iteration for prompt/logic testing
- No honeypot logs generated

### Credential Provision Mode

**Skip Reconnaissance Phase** ([config.py:17](config.py#L17)):

```python
provide_honeypot_credentials = True
```

**Effect**:
- System prompt includes target credentials (root/123456)
- Attacker can directly SSH to honeypot
- Focuses on post-exploitation tactics
- Higher session lengths, more diverse techniques

---

## Technical Challenges & Solutions

### Challenge 1: Configuration Novelty

**Problem**: RAG retrieval alone insufficient to prevent repetitive configurations.

**Solution** ([attack_pattern_check.py](Reconfigurator/attack_pattern_check.py)):
- Embed new config and all previous configs
- Compute cosine similarity
- Reject if any similarity > threshold
- Force LLM to regenerate (up to 3 attempts)

### Challenge 2: LLM Refusal

**Problem**: OpenAI models sometimes refuse offensive security tasks.

**Solution**:
- Explicit research context in prompt
- Sandboxed environment description
- Fallback to terminate gracefully ([sangria.py:118-120](Sangria/sangria.py#L118-L120))

### Challenge 3: Token Costs

**Optimizations**:
1. **OpenAI Prompt Caching**: System prompt cached across iterations
2. **Model Selection**: Use GPT-4.1-Mini for most tasks, O4-Mini only when needed
3. **Output Limits**: Truncate large command outputs to 10KB

**Monitoring**: Token usage tracked per session for budget analysis.

---

## Future Extensions

### Potential Enhancements

1. **Multi-Service Honeypots**: Currently 1 SSH service, could expand to HTTP, FTP, SMB
2. **Multi-Agent Attackers**: Parallel attackers with different strategies
3. **Defensive Blue Team**: Active defense responses to attacker actions
4. **Continuous Learning**: Use generated datasets to train better reconfigurators
5. **Real-Time Adaptation**: Dynamic honeypot responses within a session

### Research Directions

1. **Adversarial Robustness**: Can attackers learn to detect adaptive honeypots?
2. **Deception Theory**: Optimal honeypot strategy for maximum engagement
3. **Transfer Learning**: Apply learned strategies to real network defense
4. **Human-AI Comparison**: How do AI attackers differ from human red teams?

---

## Appendix: Key Algorithms

### Session Extraction Algorithm

**Input**: Full LLM conversation log
**Output**: Structured session with MITRE labels

```python
def extract_session(logs):
    session_string = ""
    tactics = []
    techniques = []
    full_session = []

    for entry in logs:
        if entry['role'] != 'assistant' or not entry['tool_calls']:
            continue

        for tool_call in entry['tool_calls']:
            if tool_call['function']['name'] != 'terminal_input':
                continue

            # Extract MITRE labels from function arguments
            args = tool_call['function']['arguments']
            tactic = args['tactic_used'].split(':')[-1]
            technique = args['technique_used'].split(':')[-1]

            # Find corresponding tool response with honeypot_logs
            tool_response = find_tool_response(logs, tool_call['id'])

            if 'honeypot_logs' in tool_response:
                for log in tool_response['honeypot_logs']:
                    if log['event']['Protocol'] == 'ssh':
                        command = log['event']['Command']

                        full_session.append({
                            'command': command,
                            'tactic': tactic,
                            'technique': technique
                        })

                        session_string += command + " "
                        tactics.append(tactic)
                        techniques.append(technique)

    return {
        'session': session_string.strip(),
        'tactics': tactics,
        'techniques': techniques,
        'length': len(tactics),
        'full_session': full_session
    }
```

### RAG-Based Config Generation Algorithm

**Input**: Previous configurations
**Output**: Novel honeypot configuration

```python
def generate_new_honeypot_config(experiment_path):
    # 1. Sample previous configs
    prev_configs = sample_previous_configs(experiment_path, n=5)

    # 2. Generate RAG query via LLM
    query_prompt = build_query_prompt(prev_configs)
    rag_query = llm(query_prompt)

    # 3. Retrieve vulnerabilities
    query_embedding = embed(rag_query)
    top_vulns = retrieve_top_k(query_embedding, vuln_db, k=5)

    # 4. Generate config via LLM
    config_prompt = build_config_prompt(top_vulns, schema)
    new_config = llm(config_prompt)

    # 5. Validate
    validate_schema(new_config, schema)

    # 6. Check novelty
    if not is_novel(new_config, prev_configs):
        return generate_new_honeypot_config(experiment_path)  # Retry

    return new_config
```

### Entropy-Based Reconfiguration Algorithm

**Input**: Stream of sessions
**Output**: Boolean (reconfigure or not)

```python
def should_reconfigure_entropy(sessions, window_size, tolerance):
    entropies = []
    technique_counter = Counter()

    for session in sessions:
        # Update technique frequencies
        technique_counter.update(session['techniques'])

        # Compute entropy
        total = sum(technique_counter.values())
        probs = [count/total for count in technique_counter.values()]
        entropy = -sum(p * log(p) for p in probs if p > 0)
        entropies.append(entropy)

    # Smooth entropy curve
    smoothed = moving_average(entropies, window_size)

    # Check if entropy plateaued (change < tolerance)
    if len(smoothed) >= 2:
        return abs(smoothed[-1] - smoothed[-2]) < tolerance
    return False
```

---

## Conclusion

Project Violet represents a novel approach to cybersecurity dataset generation through:

1. **Autonomous AI Attackers**: Replacing manual red team operations with LLM-powered agents
2. **Adaptive Honeypots**: Dynamic reconfiguration based on attack pattern analysis
3. **Closed-Loop Learning**: Continuous improvement through RAG-based evolution
4. **Automated Labeling**: MITRE ATT&CK annotations generated during attacks

The system produces high-quality, diverse attack datasets suitable for training defensive AI systems, studying adversarial behavior, and evaluating honeypot effectiveness.

**Key Innovations**:
- LLM-to-LLM adversarial interactions
- RAG-driven honeypot configuration generation
- Statistical reconfiguration criteria
- Comprehensive logging and analysis pipeline

**Applications**:
- Defensive AI training data
- Honeypot evaluation
- Attacker behavior modeling
- Adversarial ML research
