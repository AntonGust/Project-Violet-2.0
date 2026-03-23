# project-violet

## Overview

Project Violet is an automated cybersecurity research platform that simulates realistic attack scenarios against configurable honeypots to generate labeled datasets for improving defensive capabilities. The system uses AI-powered red team attacks, adaptive blue team defenses, and the Beelzebub honeypot to create a continuous feedback loop for cybersecurity improvement.

## Prerequisites

 - Docker
 - docker-compose
 - python (3.11.2+)
 - python dependencies (listed in requirements.txt)
 - .env file in top directory with api keys:
```
OPENAI_API_KEY="{your-openai-api-key}"
TOGETHER_AI_SECRET_KEY="{your-togetherai_api_key}"
"TOKENIZERS_PARALLELISM=false"
```
## Quick Start

Project Violet provides an interactive menu system for easy operation:

```bash
python main_menu.py
```

The interactive menu guides you through the complete workflow:

### 1️⃣ **Start New Experiment**
Configure and run attack simulations with customizable parameters:
- Select AI models for attacker, honeypot, and reconfigurator
- Choose reconfiguration methods (NO_RECONFIG, BASIC, ENTROPY, T_TEST)
- Set session parameters and additional options
- Configuration is automatically written to [config.py](config.py)

### 2️⃣ **Prepare Experiment Data**
Extract and process raw experiment logs for analysis:
- **Extraction Modes:**
  - `sessions.json`: Commands that reached the honeypot
  - `omni_sessions.json`: All attacker commands including reconnaissance
- Automatically combines sessions across honeypot configurations
- Creates analysis-ready datasets

### 3️⃣ **Run Purple Analysis**
Comprehensive analysis suite with multiple tools:
- **HP Comparison**: Compare session lengths and statistics across experiments
- **Meta Analysis**: Analyze MITRE tactics, honeypot deceptiveness, and attack patterns
- **Advanced Visualizations**: Generate custom plots and charts
- **Run All**: Execute all analyses in sequence

## Interactive Menu Features

The [main_menu.py](main_menu.py) provides a user-friendly interface with the following features:

### Experiment Configuration
- **Interactive Model Selection**: Choose from GPT-4.1, GPT-4.1-Mini, O4-Mini, and GPT-4.1-Nano
- **Reconfiguration Methods**: Select and configure NO_RECONFIG, BASIC, ENTROPY, or T_TEST strategies
- **Visual Confirmation**: Review all settings before starting
- **Automatic Config Updates**: Saves configuration to [config.py](config.py) automatically

### Data Preparation
- **Smart Extraction**: Choose between honeypot-only or comprehensive (omni) extraction modes
- **Multi-Experiment Support**: Process multiple experiments simultaneously
- **Progress Tracking**: Real-time status updates during extraction and combination
- **Error Handling**: Graceful handling of missing or corrupt files

### Analysis Suite
- **Prerequisite Checking**: Validates that session data exists before analysis
- **Guided Workflow**: Suggests data preparation if sessions are missing
- **Batch Analysis**: Run all analyses in sequence with a single command
- **Flexible Output**: Each analysis saves results to appropriate directories

## Configuration

### Main Configuration (`config.py`):

```python
experiment_name = "" # Name for the experiment, leave empty for timestamp.
run_id = "10" # 10 - 99, If multiple experiments are run in parallel, each need unique run_id.

# Experiment settings
llm_model_sangria = LLMModel.GPT_4_1_MINI                  # GPT_4_1, GPT_4_1_MINI, O4_MINI, GPT_4_1_NANO
llm_model_blue_lagoon = LLMModel.GPT_4_1_MINI
llm_model_reconfig = LLMModel.GPT_4_1_MINI
llm_provider_hp = "openai"                                 # openai / togetherai / static
reconfig_method: ReconfigCriteria = ReconfigCriteria.BASIC # NO_RECONFIG / BASIC / ENTROPY / T_TEST 

# Simulate HP for testing purposes
simulate_command_line = False

# Session settings
num_of_sessions = 400
max_session_length = 100

# Reconfiguration criteria settings
## Basic reconfiguration
ba_interval: int = 100

## Entropy reconfiguration
en_variable: str = "techniques"
en_window_size: int = 1
en_tolerance: float = 1e-2

## T-test reconfiguration
tt_variable: str = "tactic_sequences"
tt_tolerance: float = 0.003 # session_length: 0.008, tactics: 0.003
tt_confidence: float = 0.95

```

## Output Structure

The system generates organized output in the `logs/` directory:

```
logs/
├── [EXPERIMENT_NAME]/                  # Experiment directories
│   ├── metadata.json                  # Experiment metadata
│   ├── sessions.json                  # Combined sessions (honeypot commands)
│   ├── omni_sessions.json             # Combined sessions (all commands)
│   ├── meta_analysis/                 # Meta analysis outputs
│   │   ├── tactic_distribution.csv
│   │   ├── tactic_distribution_*.png
│   │   └── honeypot_deceptiveness.csv
│   ├── analysis_plots/                # Visualization outputs
│   │   ├── session_length_*.png
│   │   ├── mitre_distribution_*.png
│   │   └── entropy_*.png
│   └── hp_config_[N]/                 # Individual honeypot configurations
│       ├── honeypot_config.json       # Honeypot configuration used
│       ├── sessions.json              # Sessions for this config
│       ├── omni_sessions.json         # Omni sessions for this config
│       ├── tokens_used.json           # Token usage tracking
│       └── full_logs/                 # Raw attack logs
│           └── attack_[N].json        # Complete attack interaction logs
├── hp_comparison/                     # Cross-experiment comparison
│   ├── session_length_statistics.csv
│   ├── session_length_comparison_boxplot.png
│   └── session_length_mean_comparison.png
```


## Structure of code

The codebase is organized into four main components:

### ❤️ Sangria (Attacker)

* **Sangria**: AI-powered attack orchestration system
* **Tool Integration**: Automated execution of attack commands

### 💙 Blue_Lagoon (Honeypot) [Link](https://github.com/mariocandela/beelzebub)

* **Service Simulation**: Realistic vulnerable service emulation
* **Interaction Logging**: Comprehensive attack interaction capture
* **Configuration**: Iterative service modification capabilities

### ⚙️ Reconfigurator 

* **Configuration Pipeline**: Dynamic honeypot reconfiguration based on previous configurations and attack patterns
* **RAG System**: Using a RAG to retrieve vulnerabilities from NVD

### 💜 Purple

* **HP Comparison** ([hp_comparison_cli.py](Purple/Data_analysis/hp_comparison_cli.py)): Compare session lengths, statistics, and performance across multiple experiments
* **Meta Analysis** ([meta_analysis_cli.py](Purple/Data_analysis/meta_analysis_cli.py)): Analyze MITRE tactic distributions, honeypot deceptiveness, and unique attack patterns
* **Advanced Visualizations** ([run_analysis.py](Purple/Data_analysis/run_analysis.py)): Interactive plotting system for session lengths, entropy, reconfiguration criteria, and MITRE distributions

### 🛠️ Utils & Scripts

* **Session Extraction** ([Sangria/extraction.py](Sangria/extraction.py)): Extract structured session data from raw logs
* **Data Utilities** ([Utils/](Utils/)): JSON handling, logging, and metadata management
* **Automation Scripts** ([Scripts/](Scripts/)): Batch processing tools for data extraction and combination

## Workflow

```
┌─────────────────────────────────────┐
│   1. Start New Experiment           │
│   Configure & run simulations       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Raw Logs Generated                │
│   logs/EXPERIMENT/hp_config_N/      │
│   full_logs/attack_*.json           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   2. Prepare Experiment Data        │
│   Extract sessions from logs        │
│   sessions.json / omni_sessions.json│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   3. Run Purple Analysis            │
│   • HP Comparison                   │
│   • Meta Analysis                   │
│   • Advanced Visualizations         │
└─────────────────────────────────────┘
```

## Example Usage

### Running a Complete Workflow

1. **Start the interactive menu:**
   ```bash
   python main_menu.py
   ```

2. **Configure and run an experiment:**
   - Select "Start New Experiment"
   - Choose models (e.g., GPT-4.1-Mini for all components)
   - Select reconfiguration method (e.g., T_TEST)
   - Set 400 sessions with max length of 100 turns
   - Confirm and run

3. **Prepare the data:**
   - Return to main menu after experiment completes
   - Select "Prepare Experiment Data"
   - Choose extraction mode (honeypot-only or omni)
   - Select your experiment from the list
   - Confirm and process

4. **Analyze results:**
   - Select "Run Purple Analysis"
   - Choose "Run All Analyses" to generate all reports
   - Or select individual analyses as needed

### Output Examples

After running all analyses, you'll find:
- **HP Comparison**: `logs/hp_comparison/session_length_comparison_boxplot.png`
- **Meta Analysis**: `logs/EXPERIMENT_NAME/meta_analysis/tactic_distribution.csv`
- **Visualizations**: `logs/EXPERIMENT_NAME/analysis_plots/session_length_*.png`

## Troubleshooting

**Permission errors with Docker**
- Add your user to the docker group: `sudo usermod -aG docker $USER`
- Log out and back in for changes to take effect


