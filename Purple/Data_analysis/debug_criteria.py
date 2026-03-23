#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add parent directory to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from Purple.Data_analysis.utils import extract_experiment, compute_confidence_interval
from Purple.Data_analysis.metrics import measure_tactic_sequences
import numpy as np
import editdistance

logs_path = Path(__file__).resolve().parent.parent.parent / "logs"
exp_path = logs_path / "COMBINED_RECONFIG"

print("="*80)
print("DEBUGGING CRITERIA PLOT - COMBINED_RECONFIG")
print("="*80)

# Extract the experiment data
filter_empty_sessions = True
combined_sessions, sessions_list, reconfig_indices = extract_experiment(exp_path, filter_empty_sessions)

print(f"\nTotal combined sessions: {len(combined_sessions)}")
print(f"Number of configs (sessions_list): {len(sessions_list)}")
print(f"Reconfig indices: {reconfig_indices}\n")

# Show session count per config
print("Sessions per config:")
for i, sessions in enumerate(sessions_list):
    print(f"  Config {i+1}: {len(sessions)} sessions")

print("\n" + "="*80)
print("SIMULATING LEVENSHTEIN DISTANCE CONVERGENCE")
print("="*80)

# Simulate what happens in the criteria plot
config_tactic_sequences = [
    measure_tactic_sequences(sessions)["indexed_sequences"]
    for sessions in sessions_list
]

print(f"\nNumber of config_tactic_sequences: {len(config_tactic_sequences)}")

# Parameters from plot_criteria
ld_alpha = 0.05
ld_eps = 0.2

# Simulate the exact logic from criteria.py lines 30-73
criterion_indices = []
cutoff_criterion_indices = []
index_start = 0
cutoff_index_start = 0

dists_list = []  # Global distances across all configs

for config_idx, tactic_sequences in enumerate(config_tactic_sequences):
    print(f"\n{'='*60}")
    print(f"Processing Config {config_idx+1} ({len(tactic_sequences)} sessions)")
    print(f"{'='*60}")
    
    config_dists_list = []
    reconfigured = False
    broke = False
    
    for i in range(len(tactic_sequences)):
        # Calculate distances
        for j in range(0, i):
            seq_i = tactic_sequences[i]
            seq_j = tactic_sequences[j]
            if seq_i and seq_j:
                dist = editdistance.eval(seq_i, seq_j)
                dists_list.append(dist)
                config_dists_list.append(dist)
        
        # Check convergence
        if len(config_dists_list) > 1:
            config_moe = compute_confidence_interval(np.array(config_dists_list), ld_alpha)
            eps = ld_eps * np.std(config_dists_list, ddof=1)
            
            # Show first 10 sessions or when converged
            if i < 10 or config_moe < eps:
                print(f"  Session {i:3d}: MOE={config_moe:7.4f}, eps={eps:7.4f}, "
                      f"converged={str(config_moe < eps):5s}, "
                      f"config_dists={len(config_dists_list):4d}, "
                      f"global_dists={len(dists_list):4d}")
            
            # Check convergence criterion
            if config_moe < eps:
                if not reconfigured:
                    criterion_indices.append(i + index_start)
                    cutoff_criterion_indices.append(i + cutoff_index_start)
                    print(f"  >>> Criterion MET at session {i}")
                    print(f"      criterion_indices: {criterion_indices}")
                    print(f"      cutoff_criterion_indices: {cutoff_criterion_indices}")
                
                # THIS IS THE KEY PART - simulating cutoff_criterion_reconfig=True
                cutoff_criterion_reconfig = True  # This is what happens when you check the box
                if cutoff_criterion_reconfig:
                    index_start += len(tactic_sequences)
                    cutoff_index_start += i + 1
                    broke = True
                    print(f"  >>> BREAKING out of this config (cutoff_criterion_reconfig=True)")
                    print(f"      Updated index_start: {index_start}")
                    print(f"      Updated cutoff_index_start: {cutoff_index_start}")
                    break
                
                reconfigured = True
    
    if not broke:
        index_start += len(tactic_sequences)
        cutoff_index_start += len(tactic_sequences)
        print(f"  Config completed without breaking")
        print(f"      Updated index_start: {index_start}")
        print(f"      Updated cutoff_index_start: {cutoff_index_start}")

print("\n" + "="*80)
print("FINAL RESULTS")
print("="*80)
print(f"Total criterion_indices: {criterion_indices}")
print(f"Total cutoff_criterion_indices: {cutoff_criterion_indices}")
print(f"Number of convergence points found: {len(criterion_indices)}")

print("\n" + "="*80)
print("WHAT THIS MEANS FOR THE PLOTS")
print("="*80)
print(f"\nWhen 'restart_configs=True' (plots 3 & 4):")
print(f"  The plot splits data into {len(cutoff_criterion_indices)} segments")
print(f"  Each segment represents data UP TO convergence")
print(f"  Segment boundaries: {cutoff_criterion_indices}")
print(f"\nIf you're only seeing 1 graph, it means:")
print(f"  - Config 1 converged very early")
print(f"  - The 'break' stopped processing further sessions in that config")
print(f"  - Each subsequent config also converged early")
print(f"  - You have {len(cutoff_criterion_indices)} separate segments, not 13 continuous configs")
