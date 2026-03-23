import os
import glob
import json

log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
output_file = 'full_dataset.json'
all_data = []

for metadata_path in glob.glob(os.path.join(log_dir, '**/metadata.json'), recursive=True):
    run_dir = os.path.dirname(metadata_path)
    sessions_path = os.path.join(run_dir, 'sessions.json')
    experiment_type = os.path.basename(run_dir)

    if any(skip in metadata_path for skip in ['backups', 'old_experiments']):
        continue

    attacker_model = ''
    if os.path.exists(metadata_path):
        with open(metadata_path) as f:
            meta = json.load(f)
            attacker_model = meta.get('attacker_model', meta.get('llm_model_sangria',''))
            honeypot_model = meta.get('honeypot_model', meta.get ('llm_model_defend', ''))

    if os.path.exists(sessions_path):
        with open(sessions_path) as f:
            sessions = json.load(f)
            for session in sessions:
                commands = session.get('session', '')
                if not commands:
                    continue
                entry = {
                    'experiment_type': experiment_type,                    
                    'attacker_model': attacker_model,
                    'honeypot_model': honeypot_model,
                    'tactics': session.get('tactics', ''),
                    'commands': session.get('session', '')
                }
                all_data.append(entry)

with open(output_file, 'w') as f:
    json.dump(all_data, f, indent=2)

print(f"Finished {output_file}")