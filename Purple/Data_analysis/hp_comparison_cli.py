#!/usr/bin/env python3
"""
Dynamic honeypot comparison tool - compares session lengths across experiments
"""
import json
import os
import sys
from pathlib import Path
import glob

# Add parent directory to sys.path to allow imports from project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

import questionary
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t

from Purple.Data_analysis import colors

logs_path = Path(__file__).resolve().parent.parent.parent / "logs"

def compute_confidence_interval(data, confidence=0.95):
    """Compute confidence interval for the mean"""
    n = len(data)
    if n < 2:
        return np.nan, np.nan  # Can't compute CI with less than 2 points
    mean_val = np.mean(data)
    std_err = np.std(data, ddof=1) / np.sqrt(n)  # standard error
    t_crit = t.ppf((1 + confidence) / 2, df=n - 1)  # t critical value
    margin_of_error = t_crit * std_err
    return mean_val - margin_of_error, mean_val + margin_of_error

def get_session_lengths(exp_folder):
    """Get all session lengths for an experiment folder"""
    lengths = []
    
    # Look for all hp_config directories
    hp_configs = sorted(glob.glob(str(exp_folder / "hp_config_*")))
    
    if not hp_configs:
        return lengths, 0, 0
    
    total_files = 0
    valid_sessions = 0
    
    for hp_config in hp_configs:
        attack_files = glob.glob(os.path.join(hp_config, "full_logs", "attack_*.json"))
        total_files += len(attack_files)
        
        for fpath in attack_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Count assistant messages with non-null/[] tool_calls
                session_length = sum(
                    1 for entry in data
                    if isinstance(entry, dict)
                    and entry.get("role") == "assistant"
                    and entry.get("tool_calls") 
                    and isinstance(entry.get("tool_calls"), list)
                    and len(entry["tool_calls"]) > 0
                )
                
                if session_length > 0:
                    lengths.append(session_length)
                    valid_sessions += 1
            except (json.JSONDecodeError, FileNotFoundError):
                continue
    
    return lengths, total_files, valid_sessions

def main():
    # List available experiments
    all_experiments = sorted(os.listdir(logs_path))
    
    if not all_experiments:
        print("No experiments found under", logs_path)
        sys.exit(1)
    
    # Select experiments to compare
    selected_experiments = questionary.checkbox(
        "Select experiments to compare:",
        choices=all_experiments
    ).ask()
    
    if not selected_experiments:
        print("Nothing selected, exiting.")
        sys.exit(0)
    
    if len(selected_experiments) < 2:
        print("\nWarning: You selected only 1 experiment. Comparison works best with 2+ experiments.")
        proceed = questionary.confirm("Continue anyway?").ask()
        if not proceed:
            sys.exit(0)
    
    # Create output directory in logs folder
    output_dir = logs_path / "hp_comparison"
    output_dir.mkdir(exist_ok=True)
    print(f"\nOutputs will be saved to: {output_dir}")
    
    print("\n" + "="*80)
    print("HONEYPOT COMPARISON - SESSION LENGTH ANALYSIS")
    print("="*80)
    
    all_exp_lengths = []
    labels = []
    stats_data = []
    
    # Print header
    print(f"\n{'Experiment':<25} {'Files':<8} {'Valid':<8} {'Mean':<10} {'Variance':<12} "
          f"{'Std Dev':<10} {'Median':<10} {'IQR':<10} {'95% CI':<25}")
    print("-" * 130)
    
    # Process each experiment
    for name in selected_experiments:
        folder = logs_path / name
        
        if not folder.exists():
            print(f"{name:<25} Folder not found")
            continue
        
        lengths, total_files, valid_sessions = get_session_lengths(folder)
        
        if valid_sessions == 0:
            print(f"{name:<25} {total_files:<8} 0 valid sessions")
            continue
        
        # Core statistics
        mean_val = np.mean(lengths)
        var_val = np.var(lengths, ddof=1)
        std_val = np.std(lengths, ddof=1)
        
        # Median & IQR
        median_val = np.median(lengths)
        q1 = np.percentile(lengths, 25)
        q3 = np.percentile(lengths, 75)
        iqr_val = q3 - q1
        
        # 95% Confidence Interval
        ci_lower, ci_upper = compute_confidence_interval(lengths)
        
        # Store for plotting
        all_exp_lengths.append(lengths)
        labels.append(name)
        
        # Store stats
        stats_data.append({
            'Experiment': name,
            'Total Files': total_files,
            'Valid Sessions': valid_sessions,
            'Mean': mean_val,
            'Variance': var_val,
            'Std Dev': std_val,
            'Median': median_val,
            'Q1': q1,
            'Q3': q3,
            'IQR': iqr_val,
            'CI Lower': ci_lower,
            'CI Upper': ci_upper,
            'Min': np.min(lengths),
            'Max': np.max(lengths)
        })
        
        # Print summary
        print(f"{name:<25} {total_files:<8} {valid_sessions:<8} "
              f"{mean_val:<10.2f} {var_val:<12.2f} {std_val:<10.2f} "
              f"{median_val:<10.2f} {iqr_val:<10.2f} "
              f"[{ci_lower:.2f}, {ci_upper:.2f}]")
    
    if not all_exp_lengths:
        print("\nNo valid session data found for any experiment!")
        sys.exit(1)
    
    # Save statistics to CSV
    import pandas as pd
    stats_df = pd.DataFrame(stats_data)
    csv_path = output_dir / "session_length_statistics.csv"
    stats_df.to_csv(csv_path, index=False)
    print(f"\n✓ Statistics saved to: {csv_path}")
    
    # Create boxplot comparison
    print("\nGenerating comparison boxplot...")
    
    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 2), 6))
    
    # Create boxplot with custom colors
    bp = ax.boxplot(all_exp_lengths, labels=labels, showmeans=True, patch_artist=True,
                     meanprops=dict(marker='D', markerfacecolor='red', markersize=8),
                     medianprops=dict(color='black', linewidth=2))
    
    # Color each box
    for i, box in enumerate(bp['boxes']):
        box.set_facecolor(colors.scheme[i % len(colors.scheme)])
        box.set_alpha(0.6)
    
    ax.set_title("Session Length Comparison Across Experiments", fontsize=14, fontweight='bold')
    ax.set_ylabel("Commands per Session", fontsize=12)
    ax.set_xlabel("Experiment", fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    
    # Rotate labels if too many experiments
    if len(labels) > 5:
        plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    boxplot_path = output_dir / "session_length_comparison_boxplot.png"
    plt.savefig(boxplot_path, dpi=300, bbox_inches='tight')
    print(f"✓ Boxplot saved to: {boxplot_path}")
    plt.close()
    
    # Create bar chart with error bars (mean + CI)
    print("Generating mean comparison with confidence intervals...")
    
    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 1.5), 6))
    
    means = [s['Mean'] for s in stats_data]
    ci_errors = [(s['Mean'] - s['CI Lower'], s['CI Upper'] - s['Mean']) for s in stats_data]
    ci_errors_lower = [e[0] for e in ci_errors]
    ci_errors_upper = [e[1] for e in ci_errors]
    
    x_pos = np.arange(len(labels))
    bars = ax.bar(x_pos, means, yerr=[ci_errors_lower, ci_errors_upper],
                   capsize=10, alpha=0.7,
                   color=[colors.scheme[i % len(colors.scheme)] for i in range(len(labels))])
    
    ax.set_title("Mean Session Length with 95% Confidence Intervals", fontsize=14, fontweight='bold')
    ax.set_ylabel("Mean Commands per Session", fontsize=12)
    ax.set_xlabel("Experiment", fontsize=12)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    
    # Rotate labels if needed
    if len(labels) > 5:
        plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    
    barplot_path = output_dir / "session_length_mean_comparison.png"
    plt.savefig(barplot_path, dpi=300, bbox_inches='tight')
    print(f"✓ Mean comparison saved to: {barplot_path}")
    plt.close()
    
    # Statistical comparison summary
    print("\n" + "="*80)
    print("STATISTICAL COMPARISON SUMMARY")
    print("="*80)
    
    # Find experiment with longest/shortest sessions
    max_mean_idx = np.argmax(means)
    min_mean_idx = np.argmin(means)
    
    print(f"\n📊 Highest mean session length: {labels[max_mean_idx]} ({means[max_mean_idx]:.2f} commands)")
    print(f"📊 Lowest mean session length:  {labels[min_mean_idx]} ({means[min_mean_idx]:.2f} commands)")
    print(f"📊 Difference: {means[max_mean_idx] - means[min_mean_idx]:.2f} commands ({(means[max_mean_idx]/means[min_mean_idx] - 1)*100:.1f}% increase)")
    
    # Find most/least consistent
    std_devs = [s['Std Dev'] for s in stats_data]
    max_std_idx = np.argmax(std_devs)
    min_std_idx = np.argmin(std_devs)
    
    print(f"\n📈 Most variable:  {labels[max_std_idx]} (σ = {std_devs[max_std_idx]:.2f})")
    print(f"📉 Most consistent: {labels[min_std_idx]} (σ = {std_devs[min_std_idx]:.2f})")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nAll outputs saved to: {output_dir}")
    print("\nGenerated files:")
    print(f"  • {csv_path.name}")
    print(f"  • {boxplot_path.name}")
    print(f"  • {barplot_path.name}")

if __name__ == "__main__":
    main()
