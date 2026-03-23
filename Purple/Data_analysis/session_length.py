import json
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t
from scipy.stats import shapiro

# Path to your JSON file
file_path = "logs/COPY_EXPERIMENT_NO_RECONFIG_GPT_4_1_2025-07-17T21_53_49/hp_config_1/omni_sessions.json"

# Load the JSON file
with open(file_path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Extract all "length" values (number of commands per session)
all_lengths = [entry["length"] for entry in data if isinstance(entry, dict) and "length" in entry]

# Calculate stats
mean_length = np.mean(all_lengths)
variance_length = np.var(all_lengths)
variance_length_sample = np.var(all_lengths, ddof=1)
std_dev = np.std(all_lengths)

def compute_confidence_interval(session_lengths: np.ndarray, alpha: float) -> float:
    s = session_lengths.std(ddof=1)
    n = session_lengths.shape[0]

    t_crit = t.ppf(1 - alpha/2, df=n - 1)
    moe = t_crit * (s / np.sqrt(n))

    return float(moe)

confidence_interval = compute_confidence_interval(np.array(all_lengths), alpha=0.05)

print(f"All session command counts: {all_lengths}")
print(f"Mean number of commands per session: {mean_length:.2f}")
print(f"Population variance: {variance_length:.2f}")
print(f"Sample variance: {variance_length_sample:.2f}")
print(f"Standard deviation: {std_dev:.2f}")
print(f"95% confidence interval for the mean session length: ±{confidence_interval:.2f}")

# --- Normality Check ---


stat, p_value = shapiro(all_lengths)
print(f"\nShapiro-Wilk test p-value: {p_value:.4f}")
if p_value < 0.05:
    print(" Data is likely NOT normally distributed (skewed). Consider median/IQR instead of mean/std.")
else:
    print(" Data looks approximately normal.")

# --- IQR-based Outlier Detection ---
Q1 = np.percentile(all_lengths, 25)
Q3 = np.percentile(all_lengths, 75)
IQR = Q3 - Q1
iqr_outliers = [x for x in all_lengths if x > Q3 + 1.5 * IQR or x < Q1 - 1.5 * IQR]

print(f"\nIQR Outlier Detection:")
print(f"Q1 (25%): {Q1:.2f}, Q3 (75%): {Q3:.2f}, IQR: {IQR:.2f}")
print(f"Outliers based on IQR method: {iqr_outliers}")


# Detect unusually long sessions (outliers)
upper_threshold = mean_length + 2 * std_dev
long_sessions = [x for x in all_lengths if x > upper_threshold]
print(f"Sessions with unusually many commands (> {upper_threshold:.0f}): {long_sessions}")

from collections import Counter
counter = Counter(all_lengths)

# Plot histogram
plt.figure(figsize=(10, 6))
#plt.hist(all_lengths, bins=20, edgecolor='black', alpha=0.7)
plt.bar(counter.keys(), counter.values(), color='skyblue', edgecolor='black', alpha=0.7)
plt.axvline(mean_length, color='red', linestyle='dashed', linewidth=1, label=f'Mean: {mean_length:.2f}')
# add confidence interval lines
plt.axvline(mean_length - confidence_interval, color='green', linestyle='dashed', linewidth=1, label=f'95% CI Lower: {mean_length - confidence_interval:.2f}')
plt.axvline(mean_length + confidence_interval, color='green', linestyle='dashed', linewidth=1, label=f'95% CI Upper: {mean_length + confidence_interval:.2f}')
# add shadiged area for confidence interval
plt.fill_betweenx([0, max(counter.values())], 
                 mean_length - confidence_interval, 
                 mean_length + confidence_interval, 
                 color='green', alpha=0.1, label='95% CI Area')
plt.legend()
plt.title("Distribution of Commands per Session")
plt.xlabel("Number of commands in a session")
plt.ylabel("Number of sessions")
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.show()
