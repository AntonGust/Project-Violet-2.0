"""
stiches together the first configuration of each chosen experiment to a single big experiment
works because they have the same base config and sessions are independent
"""
import json
from pathlib import Path
import os
import sys
import questionary
import ipywidgets as widgets
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from Utils.jsun import load_json

logs_path = Path(__file__).resolve().parent.parent / "logs"
experiment_names = os.listdir(logs_path)[::-1]
all_experiments = sorted(experiment_names)

selected = questionary.checkbox(
    "Select experiments to combine sessions in:",
    choices=all_experiments
).ask()

selected_experiments = selected
if not selected_experiments:
    print("Nothing selected, exiting.")
    sys.exit(0)

config_paths = [logs_path / exp / "hp_config_1" for exp in selected_experiments]

# Load sessions from each experiment's first config
session_paths = [config_path / "sessions.json" for config_path in config_paths]
session_data = [load_json(path) for path in session_paths]
print(f"Loaded {len(session_data)} session files.")

flattened_sessions = []
for sessions in session_data:
    flattened_sessions.extend(sessions)

print(f"Flattened to {len(flattened_sessions)} total sessions.")

# Load tokens used from each experiment
tokens_used = []
token_paths = [logs_path / exp / "hp_config_1" / "tokens_used.json" for exp in selected_experiments]
for token_path in token_paths:
    tokens_used.append(load_json(token_path))

flattened_tokens_used = []
for tokens in tokens_used:
    flattened_tokens_used.extend(tokens)

configs = [load_json(config_path / "honeypot_config.json") for config_path in config_paths]

unique_configs = {json.dumps(config, sort_keys=True) for config in configs}
if len(unique_configs) > 1:
    print("WARNING: Configs are not the same across experiments!")
    sys.exit(1)
else:
    print("All configs are the same across experiments.")

honeypot_config = configs[0]  # Take the first one, they are all the same

# Get metadata from the first experiment
metadata_path = logs_path / selected_experiments[0] / "metadata.json"
metadata = load_json(metadata_path)

# Create new experiment directory
new_experiment_name = "BASE_CONFIG_COMBINED"
new_experiment_path = logs_path / new_experiment_name / "hp_config_1"

os.makedirs(new_experiment_path, exist_ok=True)
with open(new_experiment_path / "sessions.json", 'w') as f:
    json.dump(flattened_sessions, f, indent=2)
with open(new_experiment_path / "tokens_used.json", 'w') as f:
    json.dump(flattened_tokens_used, f, indent=2)
with open(new_experiment_path / "honeypot_config.json", 'w') as f:
    json.dump(honeypot_config, f, indent=2)
with open(new_experiment_path.parent / 'sessions.json', 'w') as f:
    json.dump(flattened_sessions, f, indent=2)
with open(new_experiment_path.parent / 'metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

