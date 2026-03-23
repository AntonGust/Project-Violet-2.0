#!/usr/bin/env python3
"""
Generate attack interaction summary from full_logs JSON files.
Replicates the format found in "attack_interaction_summary.txt".

This script analyzes attack logs and creates a ranked summary showing:
- Number of interactions per attack
- Total character count
- Average characters per interaction

USAGE:
    python3 generate_interaction_summary.py

The script will:
1. Scan the Big_Ass_Dataset directory for experiments
2. Ask which experiments to analyze (or 'all')
3. Count interactions and character metrics for each attack
4. Generate a ranked summary sorted by interaction count

INPUT:
    - Reads from: Big_Ass_Dataset/[EXPERIMENT]/hp_config_*/full_logs/attack_*.json

OUTPUT:
    - Creates: attack_interaction_summary.txt
    - Contains ranked list of attacks by interaction count
    - Shows total attacks processed and grand total interactions

EXAMPLE OUTPUT:
    Attack Interaction Summary (sorted by number of interactions)
    Generated: 2025-12-01 10:30:00
    ====================================================================================================

    Total attacks processed: 1275
    Grand total interactions: 55355

    rank  interactions   total_chars   avg_chars             hp_folder  file
    ------------------------------------------------------------------------------------------------------------------------
       1           120        100606       838.4  hp_config_12          attack_66
       2           118        106388       901.6  hp_config_2           attack_100
       ...
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import sys


def load_json(file_path: Path):
    """Load JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def count_interactions_and_chars(attack_file: Path) -> Tuple[int, int]:
    """
    Count the number of interactions and total characters in an attack log.

    Returns:
        Tuple of (interaction_count, total_chars)
    """
    try:
        attack_data = load_json(attack_file)

        interaction_count = 0
        total_chars = 0

        for message in attack_data:
            role = message.get('role')

            # Count assistant messages with tool calls as interactions
            if role == 'assistant':
                tool_calls = message.get('tool_calls')
                if tool_calls:
                    interaction_count += len(tool_calls)

            # Count characters in tool responses
            if role == 'tool':
                content = message.get('content', '')
                if content:
                    total_chars += len(str(content))

        return interaction_count, total_chars

    except Exception as e:
        print(f"  ⚠ Error processing {attack_file.name}: {e}")
        return 0, 0


def analyze_experiment(experiment_path: Path) -> List[Dict]:
    """
    Analyze all attack logs in an experiment.

    Returns:
        List of dictionaries with attack statistics
    """
    results = []

    # Find all hp_config directories
    config_dirs = sorted([d for d in experiment_path.iterdir()
                         if d.is_dir() and d.name.startswith('hp_config')],
                        key=lambda x: int(x.name.split('_')[-1]))

    for config_dir in config_dirs:
        hp_folder = config_dir.name
        full_logs_path = config_dir / "full_logs"

        if not full_logs_path.exists():
            continue

        # Process each attack file
        attack_files = [f for f in full_logs_path.iterdir()
                       if f.suffix == '.json' and f.name.startswith('attack_')]

        print(f"  Analyzing {hp_folder} ({len(attack_files)} attacks)...")

        for attack_file in attack_files:
            interaction_count, total_chars = count_interactions_and_chars(attack_file)

            if interaction_count > 0:
                avg_chars = total_chars / interaction_count
            else:
                avg_chars = 0

            results.append({
                'hp_folder': hp_folder,
                'file': attack_file.stem,  # e.g., "attack_100"
                'interactions': interaction_count,
                'total_chars': total_chars,
                'avg_chars': avg_chars
            })

    return results


def generate_summary(all_results: List[Dict], output_path: Path) -> None:
    """Generate the interaction summary report."""

    # Sort by interaction count (descending), then by total_chars (descending)
    sorted_results = sorted(all_results,
                          key=lambda x: (x['interactions'], x['total_chars']),
                          reverse=True)

    # Calculate totals
    total_attacks = len(sorted_results)
    grand_total_interactions = sum(r['interactions'] for r in sorted_results)

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build output
    lines = []
    lines.append("Attack Interaction Summary (sorted by number of interactions)")
    lines.append(f"Generated: {timestamp}")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"Total attacks processed: {total_attacks}")
    lines.append(f"Grand total interactions: {grand_total_interactions}")
    lines.append("")
    lines.append("rank  interactions   total_chars   avg_chars             hp_folder  file")
    lines.append("-" * 120)

    # Add ranked results
    for rank, result in enumerate(sorted_results, 1):
        line = f"{rank:4d}  {result['interactions']:12d}  {result['total_chars']:12d}  {result['avg_chars']:10.1f}  {result['hp_folder']:16s}  {result['file']}"
        lines.append(line)

    # Write output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n✓ Summary written to: {output_path}")
    print(f"  Total attacks: {total_attacks}")
    print(f"  Grand total interactions: {grand_total_interactions}")


def main():
    """Main entry point."""
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATASET_PATH = BASE_DIR / "Big_Ass_Dataset"

    # Find all experiment directories
    experiment_dirs = sorted([d for d in DATASET_PATH.iterdir()
                             if d.is_dir() and not d.name.startswith('.')])

    print("=" * 80)
    print("Attack Interaction Summary Generator")
    print("Analyzes attack logs and generates interaction statistics")
    print("=" * 80)
    print(f"\nDataset path: {DATASET_PATH}")
    print(f"Found {len(experiment_dirs)} experiment directories")

    # Ask user which experiments to process
    print("\nAvailable experiments:")
    for i, exp_dir in enumerate(experiment_dirs, 1):
        print(f"  {i}. {exp_dir.name}")

    print("\nEnter experiment numbers to analyze (comma-separated, or 'all'):")
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

    # Ask for output file location
    print("\nOutput file name:")
    print("  Default: 'attack_interaction_summary.txt' (in Big_Ass_Dataset/)")
    output_name = input("> ").strip() or "attack_interaction_summary.txt"
    output_path = DATASET_PATH / output_name

    # Analyze all selected experiments
    all_results = []

    for experiment_path in selected_experiments:
        print(f"\n>> Analyzing experiment: {experiment_path.name}")
        results = analyze_experiment(experiment_path)
        all_results.extend(results)

    # Generate summary report
    print("\n" + "=" * 80)
    print("Generating summary report...")
    print("=" * 80)

    generate_summary(all_results, output_path)

    print("\n" + "=" * 80)
    print("Done!")
    print("=" * 80)


if __name__ == "__main__":
    main()
