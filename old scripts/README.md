# Scripts

These scripts are here to help out in doing medial tasks. This includes

- `combine_sessions.py`: takes individual `sessions.json` files for each config in an experiment and combines them into a single long file.
- `download_logs.py`: allows you to select individual experiments on the IBM cloud to download locally.
- `extract_all_logs.py`: allows you to extract relevant data into `session.json`files from the raw data in the `attack_*.json` files again. This is useful if you change what data is extracted after an experiment has been run.
- `extract_attack_justifications_V4.py`: extracts final justifications from attack sessions with bullet point validation.
- `format_attack_logs.py`: formats full_logs JSON files into human-readable text format, reproducing the format found in "Attack Content Summaries" folder.
- `generate_interaction_summary.py`: generates attack interaction summary with rankings by interaction count, total characters, and average characters per interaction.
- `stich_experiments.py`: ask Nils lol
