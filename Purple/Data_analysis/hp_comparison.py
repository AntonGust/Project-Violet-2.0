import json, glob, os
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t

#  Compute 95% Confidence Interval for the mean
def compute_confidence_interval(data, confidence=0.95):
    n = len(data)
    if n < 2:
        return np.nan, np.nan  # Can't compute CI with less than 2 points
    mean_val = np.mean(data)
    std_err = np.std(data, ddof=1) / np.sqrt(n)  # standard error
    t_crit = t.ppf((1 + confidence) / 2, df=n - 1)  # t critical value
    margin_of_error = t_crit * std_err
    return mean_val - margin_of_error, mean_val + margin_of_error

#  Get all session lengths for an experiment folder
def get_session_lengths(exp_folder):
    lengths = []
    
    attack_files = glob.glob(os.path.join(exp_folder, "hp_config_1", "full_logs", "attack_*.json"))
    total_files = len(attack_files)
    
    if total_files == 0:
        return lengths, total_files, 0  # No files found
    
    valid_sessions = 0
    
    for fpath in attack_files:
        with open(fpath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue  # skip invalid JSON
        
            #  Only count assistant messages with non-null/[] tool_calls
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
    
    return lengths, total_files, valid_sessions

#  Experiment folders
ROOT = "/home/defend/project-violet/logs"
experiments = {
    "GPT4": os.path.join(ROOT, "EXPERIMENT_HP_4_1_2025-07-21T19_34_44"),
    "4.1Mini": os.path.join(ROOT, "EXPERIMENT_HP_4_1_MINI_2025-07-21T19_31_55"),
    "LLAMA70B": os.path.join(ROOT, "EXPERIMENT_HP_LLAMA70B_2025-07-22T14_46_57"),
    "Static": os.path.join(ROOT, "EXPERIMENT_HP_STATIC_2025-07-21T19_32_44"),
    "O4_MINI": os.path.join(ROOT, "EXPERIMENT_HP_O4_MINI_2025-07-21T20_30_40")
}

all_exp_lengths = []
labels = []

#  Print header with CI column
print("\n Experiment Summary:")
print(f"{'Model':<10} {'Files':<8} {'Valid':<8} {'Mean':<10} {'Variance':<12} {'Std Dev':<10} "
      f"{'Median':<10} {'IQR':<10} {'95% CI':<25}")

#  Loop through experiments and compute stats
for name, folder in experiments.items():
    if not os.path.exists(folder):
        print(f"{name:<10} Folder not found: {folder}")
        continue
    
    lengths, total_files, valid_sessions = get_session_lengths(folder)
    
    if valid_sessions == 0:
        print(f"{name:<10} {total_files:<8} 0 valid sessions")
        continue
    
    #  Core stats
    mean_val = np.mean(lengths)
    var_val = np.var(lengths, ddof=1)
    std_val = np.std(lengths, ddof=1)
    
    #  Median & IQR
    median_val = np.median(lengths)
    q1 = np.percentile(lengths, 25)
    q3 = np.percentile(lengths, 75)
    iqr_val = q3 - q1
    
    #  95% Confidence Interval
    ci_lower, ci_upper = compute_confidence_interval(lengths)
    
    # Print summary with CI
    print(f"{name:<10} {total_files:<8} {valid_sessions:<8} "
          f"{mean_val:<10.2f} {var_val:<12.2f} {std_val:<10.2f} "
          f"{median_val:<10.2f} {iqr_val:<10.2f} "
          f"[{ci_lower:.2f}, {ci_upper:.2f}]")
    
    all_exp_lengths.append(lengths)
    labels.append(name)

#  Boxplot for comparison
if all_exp_lengths:
    plt.figure(figsize=(10,6))
    plt.boxplot(all_exp_lengths, labels=labels, showmeans=True)
    plt.title("Session Length Comparison (Number of commands per Session)")
    plt.ylabel("commands per session")
    plt.grid(axis="y", linestyle="--", alpha=0.7)

    output_path = "/home/defend/project-violet/Purple/Data_analysis/comparison_boxplot.png"
    plt.savefig(output_path)
    print(f"\n  Comparison plot saved as {output_path}")
else:
    print("\n  No valid session data found for any experiment!")