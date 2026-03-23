#!/usr/bin/env python3
"""
Format full_logs JSON files into human-readable text format.
Reproduces the format found in "Attack Content Summaries" folder.

This script processes attack logs from the Big_Ass_Dataset and formats them
into readable text files with interaction details, tool calls, and responses.

USAGE:
    python3 format_attack_logs.py

The script will:
1. Scan the Big_Ass_Dataset directory for experiments
2. Ask which experiments you want to process (or 'all')
3. Ask for the output directory name (default: 'Attack_Content_Summaries')
4. Process each attack log and create formatted .txt files

INPUT:
    - Reads from: Big_Ass_Dataset/[EXPERIMENT]/hp_config_*/full_logs/attack_*.json
    - Uses honeypot_config.json from each hp_config directory for context

OUTPUT:
    - Writes to: Big_Ass_Dataset/[OUTPUT_DIR]/[EXPERIMENT]/hp_config_*/attack_*.txt
    - Each .txt file contains:
        * Honeypot configuration and prompt
        * Formatted interaction log with tool calls and responses
        * Assistant reasoning/explanations between actions

EXAMPLE:
    $ python3 format_attack_logs.py
    Available experiments:
      1. COMBINED_00
      2. COMBINED_RECONFIG

    Enter experiment numbers to process (comma-separated, or 'all'):
    > 1

    Output directory name (will be created in Big_Ass_Dataset/):
      Default: 'Attack_Content_Summaries'
    > My_Formatted_Logs

    >> Processing experiment: COMBINED_00
      Processing hp_config_1 (506 attacks)...
        ✓ Formatted attack_100.json -> COMBINED_00/hp_config_1/attack_100.txt
        ...
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import sys


def load_json(file_path: Path) -> Any:
    """Load JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_honeypot_info(config_path: Path) -> Dict[str, str]:
    """Extract honeypot configuration information."""
    try:
        config = load_json(config_path)
        if 'services' in config and len(config['services']) > 0:
            service = config['services'][0]
            plugin = service.get('plugin', {})

            return {
                'protocol': service.get('protocol', 'unknown'),
                'address': service.get('address', 'unknown'),
                'model': plugin.get('llmModel', 'unknown'),
                'cve_tags': service.get('cveTags', 'None'),
                'cve_description': service.get('cveDescription', ''),
                'description': config.get('description', ''),
                'prompt': plugin.get('prompt', '')
            }
    except Exception as e:
        print(f"Warning: Could not load honeypot config: {e}")

    return {
        'protocol': 'unknown',
        'address': 'unknown',
        'model': 'unknown',
        'cve_tags': 'None',
        'cve_description': '',
        'description': '',
        'prompt': ''
    }


def format_tool_call(tool_call: Dict) -> str:
    """Format a tool call from assistant message."""
    if not tool_call:
        return "[none]"

    func = tool_call.get('function', {})
    args = func.get('arguments', {})

    # Handle string arguments (need to parse JSON)
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except:
            return args

    # Extract the actual command/input
    if isinstance(args, dict):
        return args.get('input', args.get('command', str(args)))

    return str(args)


def clean_terminal_output(text: str) -> str:
    """Clean terminal output by preserving ANSI codes but formatting nicely."""
    if not text:
        return "[no output captured]"
    return str(text)


def format_attack_log(attack_file: Path, config_path: Path, hp_folder: str, output_path: Path) -> None:
    """Format a single attack log file into readable text format."""

    # Load attack data
    attack_data = load_json(attack_file)
    hp_info = extract_honeypot_info(config_path)

    # Start building output
    output_lines = []

    # Header with honeypot context
    output_lines.append("=== Honeypot Prompt Context ===")
    output_lines.append(f"Protocol: {str(hp_info['protocol'])}")
    output_lines.append(f"Address: {str(hp_info['address'])}")
    output_lines.append(f"Model: {str(hp_info['model'])}")
    output_lines.append(f"CVE Tags: {str(hp_info['cve_tags'])}")
    output_lines.append(f"CVE Description: {str(hp_info['cve_description'])}")
    output_lines.append(f"Description: {str(hp_info['description'])}")
    output_lines.append("")
    output_lines.append("Prompt:")
    output_lines.append(str(hp_info['prompt']))
    output_lines.append("=" * 80)
    output_lines.append("")

    # Attack summary header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_lines.append(f"Attack summary for {attack_file.name} ({hp_folder}) — generated {timestamp}")
    output_lines.append("-" * 80)
    output_lines.append("")
    output_lines.append("")

    # Process interactions
    interaction_num = 0

    for i, message in enumerate(attack_data):
        role = message.get('role')
        content = message.get('content')

        # Skip system messages (already included in header)
        if role == 'system':
            continue

        # Skip initial user "What is your next move?" message
        if role == 'user' and content and 'next move' in content.lower():
            continue

        # Process assistant messages with tool calls
        if role == 'assistant':
            tool_calls = message.get('tool_calls')

            if tool_calls:
                # This starts a new interaction
                for tool_call in tool_calls:
                    interaction_num += 1

                    output_lines.append("=" * 231)
                    output_lines.append("")
                    output_lines.append(f"Interaction #{interaction_num}")
                    output_lines.append(f"Tool Call ID: {tool_call.get('id', 'unknown')}")
                    output_lines.append("Tool input:")

                    tool_input = format_tool_call(tool_call)
                    output_lines.append(tool_input)
                    output_lines.append("")

                    # Look ahead for the tool response
                    tool_call_id = tool_call.get('id')
                    for j in range(i + 1, len(attack_data)):
                        next_msg = attack_data[j]
                        if next_msg.get('role') == 'tool' and next_msg.get('tool_call_id') == tool_call_id:
                            output_lines.append("Tool output:")
                            tool_output = clean_terminal_output(next_msg.get('content', ''))
                            output_lines.append(tool_output)
                            output_lines.append("")
                            break

            # Assistant's text response (reasoning/explanation)
            if content:
                output_lines.append("Assistant reply:")
                output_lines.append(str(content))
                output_lines.append("")
                output_lines.append("-" * 60)
                output_lines.append("")

    # Write output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"  ✓ Formatted {attack_file.name} -> {output_path.relative_to(output_path.parent.parent.parent)}")


def process_experiment(experiment_path: Path, output_base: Path) -> None:
    """Process all attack logs in an experiment."""

    experiment_name = experiment_path.name
    print(f"\n>> Processing experiment: {experiment_name}")

    # Find all hp_config directories
    config_dirs = sorted([d for d in experiment_path.iterdir()
                         if d.is_dir() and d.name.startswith('hp_config')],
                        key=lambda x: int(x.name.split('_')[-1]))

    for config_dir in config_dirs:
        hp_folder = config_dir.name
        full_logs_path = config_dir / "full_logs"
        config_file = config_dir / "honeypot_config.json"

        if not full_logs_path.exists():
            print(f"  ⚠ Skipping {hp_folder}: no full_logs directory")
            continue

        if not config_file.exists():
            print(f"  ⚠ Warning: no honeypot_config.json for {hp_folder}")

        # Process each attack file
        attack_files = sorted([f for f in full_logs_path.iterdir()
                              if f.suffix == '.json' and f.name.startswith('attack_')],
                             key=lambda x: int(x.stem.split('_')[-1]))

        print(f"  Processing {hp_folder} ({len(attack_files)} attacks)...")

        for attack_file in attack_files:
            output_path = output_base / experiment_name / hp_folder / attack_file.with_suffix('.txt').name
            format_attack_log(attack_file, config_file, hp_folder, output_path)


def main():
    """Main entry point."""
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATASET_PATH = BASE_DIR / "Big_Ass_Dataset"

    # Find all experiment directories
    experiment_dirs = sorted([d for d in DATASET_PATH.iterdir()
                             if d.is_dir() and not d.name.startswith('.')])

    print("=" * 80)
    print("Attack Log Formatter")
    print("Formats full_logs JSON files into human-readable text")
    print("=" * 80)
    print(f"\nDataset path: {DATASET_PATH}")
    print(f"Found {len(experiment_dirs)} experiment directories")

    # Ask user which experiments to process
    print("\nAvailable experiments:")
    for i, exp_dir in enumerate(experiment_dirs, 1):
        print(f"  {i}. {exp_dir.name}")

    print("\nEnter experiment numbers to process (comma-separated, or 'all'):")
    user_input = input("> ").strip()

    if user_input.lower() == 'all':
        selected_experiments = experiment_dirs
    else:
        try:
            indices = [int(x.strip()) - 1 for x in user_input.split(',')]
            selected_experiments = [experiment_dirs[i] for i in indices]
        except (ValueError, IndexError):
            print("Invalid input. Exiting.")
            sys.exit(1)

    # Ask for output directory
    print("\nOutput directory name (will be created in Big_Ass_Dataset/):")
    print("  Default: 'Attack_Content_Summaries'")
    output_name = input("> ").strip() or "Attack_Content_Summaries"
    output_base = DATASET_PATH / output_name

    # Process selected experiments
    for experiment_path in selected_experiments:
        process_experiment(experiment_path, output_base)

    print("\n" + "=" * 80)
    print(f"✓ Done! Formatted logs saved to: {output_base}")
    print("=" * 80)


if __name__ == "__main__":
    main()
