#!/usr/bin/env python3
"""
Command-line version of meta_analysis for running outside Jupyter
"""
import os
import sys
from pathlib import Path

# Add parent directory to sys.path to allow imports from project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

import questionary
import numpy as np
import json
import matplotlib.pyplot as plt
import editdistance
import pandas as pd
from collections import Counter

from Purple.Data_analysis import colors
from Purple.Data_analysis.utils import extract_experiment, compute_confidence_interval
from Purple.Data_analysis.metrics import (
    measure_session_length, 
    measure_mitre_distribution,
    measure_tactic_sequences
)

logs_path = Path(__file__).resolve().parent.parent.parent / "logs"

def main():
    # List available experiments
    all_experiments = sorted(os.listdir(logs_path))
    
    if not all_experiments:
        print("No experiments found under", logs_path)
        sys.exit(1)
    
    # Select experiments
    selected_experiments = questionary.checkbox(
        "Select experiments to analyze:",
        choices=all_experiments
    ).ask()
    
    if not selected_experiments:
        print("Nothing selected, exiting.")
        sys.exit(0)
    
    print(f"\nAnalyzing {len(selected_experiments)} experiments...")
    
    # Create output directory in the first selected experiment
    output_dir = logs_path / selected_experiments[0] / "meta_analysis"
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutputs will be saved to: {output_dir}")
    
    filter_empty_sessions = True
    paths = [logs_path / exp for exp in selected_experiments]
    
    # Load data
    sessions_list_list = []
    combined_sessions_list = []
    reconfig_indices_list = []
    
    for path in paths:
        print(f"Loading {path.name}...")
        combined_sessions, sessions_list, reconfig_indices = extract_experiment(path, filter_empty_sessions)
        sessions_list_list.append(sessions_list)
        combined_sessions_list.append(combined_sessions)
        reconfig_indices_list.append(reconfig_indices)
    
    # ========================================
    # 1. TACTIC DISTRIBUTION ANALYSIS
    # ========================================
    print("\n" + "="*60)
    print("TACTIC DISTRIBUTION ANALYSIS")
    print("="*60)
    
    full_tactic_distributions = {}
    tactic_distributions = []
    session_lengths = []
    
    for i, sessions in enumerate(combined_sessions_list):
        mitre_dist_data = measure_mitre_distribution(sessions)
        tactics = mitre_dist_data["tactics"]
        
        for tactic, count in tactics.items():
            if tactic not in full_tactic_distributions:
                full_tactic_distributions[tactic] = 0
            full_tactic_distributions[tactic] += count
        
        tactic_distributions.append(tactics)
        session_lengths.append(measure_session_length(sessions))
    
    # Sort by count
    full_tactic_distributions = dict(sorted(full_tactic_distributions.items(), key=lambda x: x[1], reverse=True))
    
    print("\nTotal Tactic Distribution:")
    for tactic, count in full_tactic_distributions.items():
        print(f"  {tactic}: {count}")
    
    # Plot tactic distribution
    plt.figure(figsize=(10, 6))
    plt.bar(full_tactic_distributions.keys(), full_tactic_distributions.values(), color=colors.blue)
    plt.xlabel("Tactic")
    plt.ylabel("Count")
    plt.title("Tactic Distribution Across All Experiments")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_dir / "tactic_distribution_total.png", dpi=300, bbox_inches='tight')
    print(f"\nSaved: {output_dir / 'tactic_distribution_total.png'}")
    plt.close()
    
    # Stacked bar chart
    plt.figure(figsize=(12, 6))
    all_tactics = list(full_tactic_distributions.keys())
    x_positions = np.arange(len(all_tactics))
    bottom = np.zeros(len(all_tactics))
    
    for i, tactic_distribution in enumerate(tactic_distributions):
        counts = [tactic_distribution.get(tactic, 0) for tactic in all_tactics]
        plt.bar(x_positions, counts, 
                bottom=bottom,
                label=f'{selected_experiments[i]}',
                color=colors.scheme[i % len(colors.scheme)])
        bottom += counts
    
    plt.xlabel("Tactic")
    plt.ylabel("Count")
    plt.title("Tactic Distribution Across All Experiments (Stacked)")
    plt.xticks(x_positions, all_tactics, rotation=45, ha='right')
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "tactic_distribution_stacked.png", dpi=300, bbox_inches='tight')
    print(f"Saved: {output_dir / 'tactic_distribution_stacked.png'}")
    plt.close()
    
    # Create tactic distribution table
    tactic_distribution_df = pd.DataFrame(tactic_distributions)
    tactic_distribution_df["session_length"] = [sl['mean'] for sl in session_lengths]
    tactic_distribution_df["experiment"] = selected_experiments
    tactic_distribution_df = tactic_distribution_df.set_index("experiment")
    tactic_distribution_df = tactic_distribution_df.reindex(columns=["session_length"] + list(full_tactic_distributions.keys()))
    tactic_distribution_df = tactic_distribution_df.fillna(0)
    
    # Add total column and convert to percentages
    tactic_distribution_df["total"] = tactic_distribution_df.drop(columns=['session_length']).sum(axis=1)
    for col in full_tactic_distributions.keys():
        tactic_distribution_df[col] = (tactic_distribution_df[col] / tactic_distribution_df["total"] * 100).round(2)
    
    # Add totals row
    tactic_distribution_df.loc["Average"] = tactic_distribution_df.mean(numeric_only=True)
    tactic_distribution_df = tactic_distribution_df.round(2)
    
    print("\nTactic Distribution Table (%):")
    print(tactic_distribution_df)
    
    tactic_distribution_df.to_csv(output_dir / "tactic_distribution.csv")
    print(f"\nSaved: {output_dir / 'tactic_distribution.csv'}")
    
    # ========================================
    # 2. HONEYPOT DECEPTIVENESS
    # ========================================
    print("\n" + "="*60)
    print("HONEYPOT DECEPTIVENESS ANALYSIS")
    print("="*60)
    
    hp_deceptiveness_data = []
    for i, sessions_list in enumerate(combined_sessions_list):
        n_experiments = len(sessions_list)
        
        honeypot_detected = sum(1 for session in sessions_list if session.get("discovered_honeypot") == "yes")
        honeypot_not_detected = n_experiments - honeypot_detected
        
        detected_percentage = honeypot_detected / n_experiments * 100 if n_experiments > 0 else 0
        not_detected_percentage = honeypot_not_detected / n_experiments * 100 if n_experiments > 0 else 0
        
        session_length_data = measure_session_length(sessions_list)
        average_session_length = session_length_data["mean"]
        
        sessions_before_discovery = [session for session in sessions_list if session.get("discovered_honeypot") == "yes"]
        if sessions_before_discovery:
            session_length_before_discovery = measure_session_length(sessions_before_discovery)
            average_session_length_before_discovery = session_length_before_discovery["mean"]
        else:
            average_session_length_before_discovery = 0
        
        sessions_without_discovery = [session for session in sessions_list if session.get("discovered_honeypot") == "no"]
        if sessions_without_discovery:
            session_length_without_discovery = measure_session_length(sessions_without_discovery)
            average_session_length_without_discovery = session_length_without_discovery["mean"]
        else:
            average_session_length_without_discovery = 0
        
        hp_deceptiveness_data.append({
            "Experiment": selected_experiments[i],
            "Detection %": detected_percentage,
            "No Detection %": not_detected_percentage,
            "Avg Session Length": average_session_length,
            "Avg Length (Discovered)": average_session_length_before_discovery,
            "Avg Length (Not Discovered)": average_session_length_without_discovery
        })
    
    hp_deceptiveness_df = pd.DataFrame(hp_deceptiveness_data)
    hp_deceptiveness_df = hp_deceptiveness_df.round(2)
    
    print("\nHoneypot Deceptiveness:")
    print(hp_deceptiveness_df.to_string(index=False))
    
    hp_deceptiveness_df.to_csv(output_dir / "honeypot_deceptiveness.csv", index=False)
    print(f"\nSaved: {output_dir / 'honeypot_deceptiveness.csv'}")
    
    # ========================================
    # 3. UNIQUE SESSIONS OVER TIME
    # ========================================
    print("\n" + "="*60)
    print("UNIQUE SESSIONS ANALYSIS")
    print("="*60)
    
    unique_session_list_list = []
    for i, comb_session in enumerate(combined_sessions_list):
        unique_session = set()
        _usll = []
        for session in comb_session:
            unique_session.add(session['tactics'])
            _usll.append(len(unique_session))
        unique_session_list_list.append(_usll)
        print(f"\n{selected_experiments[i]}: {len(unique_session)} unique sessions")
    
    plt.figure(figsize=(12, 6))
    for i, usl in enumerate(unique_session_list_list):
        plt.plot(usl, marker='o', linestyle='-', label=selected_experiments[i], 
                color=colors.scheme[i % len(colors.scheme)])
    plt.xlabel("Session Index")
    plt.ylabel("Number of Unique Sessions")
    plt.title("Number of Unique Sessions Over Time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / "unique_sessions_over_time.png", dpi=300, bbox_inches='tight')
    print(f"\nSaved: {output_dir / 'unique_sessions_over_time.png'}")
    plt.close()
    
    print("\n" + "="*60)
    print("ANALYSIS COMPLETE")
    print("="*60)
    print(f"\nAll outputs saved to: {output_dir}")

if __name__ == "__main__":
    main()
