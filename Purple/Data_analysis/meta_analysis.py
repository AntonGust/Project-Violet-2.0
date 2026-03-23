# %%
import os
import sys
from pathlib import Path

# Add parent directory to sys.path to allow imports from project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

import questionary
import numpy as np
import ipywidgets as widgets
from IPython.display import display
import json
import pprint
import matplotlib.pyplot as plt
import editdistance

from Purple.Data_analysis.plots.heatmaps import plot_heatmaps
from Purple.Data_analysis.plots.session_length import plot_session_length
from Purple.Data_analysis import colors
from Purple.RagData.retrive_techniques import retrieve_unique_techniques
from Purple.Data_analysis.utils import extract_experiment, compute_confidence_interval

logs_path = Path(__file__).resolve().parent.parent.parent / "logs"
experiment_names = os.listdir(logs_path)[::-1]

# %%
all_experiments = sorted(experiment_names)

# Create interactive widget for Jupyter notebook
experiment_selector = widgets.SelectMultiple(
    value=[],
    style={'description_width': 'initial'},
    options=all_experiments,
    description='Experiments:',
    disabled=False,
    layout=widgets.Layout(width='auto', height='200px'),
    rows=10
)

display(experiment_selector)

# To get selected values, use: experiment_selector.value

# %%
from Utils.jsun import load_json
import numpy as np
from Purple.Data_analysis.metrics import measure_session_length, measure_mitre_distribution, \
    measure_entropy_session_length, measure_entropy_techniques, measure_entropy_tactics

filter_empty_sessions = True
# %%

selected_experiments = list(experiment_selector.value)
if not selected_experiments:
    print("Nothing selected, exiting.")
    sys.exit(0)

paths = [logs_path / exp for exp in selected_experiments]
print(paths)

sessions_list_list = []
combined_sessions_list = []
reconfig_indices_list = []
for path in paths:
    combined_sessions, sessions_list, reconfig_indices = extract_experiment(path, filter_empty_sessions)
    sessions_list_list.append(sessions_list)
    combined_sessions_list.append(combined_sessions)
    reconfig_indices_list.append(reconfig_indices)

print(json.dumps(sessions_list_list, indent=2))

# %% Tactic distribution
from Purple.Data_analysis.metrics import measure_tactic_sequences, measure_technique_sequences, measure_command_sequences
for i, combined_sessions in enumerate(combined_sessions_list):
    sequence_data = measure_tactic_sequences(combined_sessions)

    full_tactic_distributions = {}
    tactic_distributions = []
    session_lengths = []

for i, sessions in enumerate(combined_sessions_list):
    mitre_dist_data = measure_mitre_distribution(sessions)
    tactics = list(mitre_dist_data["tactics"])
    print(mitre_dist_data["tactics"])

    # add to all fields in full_tactic_distributions with the number and tactic in tactics
    for tactic in tactics:
        if tactic not in full_tactic_distributions:
            full_tactic_distributions[tactic] = 0
        full_tactic_distributions[tactic] += mitre_dist_data["tactics"][tactic]

    tactic_distributions.append(mitre_dist_data["tactics"])
    session_lengths.append(measure_session_length(sessions))

# Sort by count in descending order
full_tactic_distributions = dict(sorted(full_tactic_distributions.items(), key=lambda x: x[1], reverse=True))
print(full_tactic_distributions)
print(tactic_distributions)
print(session_lengths)

# %% Plot tactic distribution
plt.figure(figsize=(10, 6))
plt.bar(full_tactic_distributions.keys(), full_tactic_distributions.values(), color=colors.blue)
plt.xlabel("Tactic")
plt.ylabel("Count")
plt.title("Tactic Distribution Across All Experiments")
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.show()

# %% plot tactic distribution for all experiments with different colors in a single plot
plt.figure(figsize=(12, 6))

# Get all unique tactics across all experiments and sort by total count (descending)
all_tactics = sorted(full_tactic_distributions.keys(), key=lambda x: full_tactic_distributions[x], reverse=True)

# Set up bar positions
x_positions = np.arange(len(all_tactics))

# Initialize bottom array for stacking
bottom = np.zeros(len(all_tactics))

for i, tactic_distribution in enumerate(tactic_distributions):
    # Get counts for each tactic (0 if not present)
    counts = [tactic_distribution.get(tactic, 0) for tactic in all_tactics]
    
    # Plot stacked bars
    plt.bar(x_positions, counts, 
            bottom=bottom,
            label=f'Experiment {selected_experiments[i]}',
            color=colors.scheme[i % len(colors.scheme)],)
    
    # Update bottom for next stack
    bottom += counts

plt.xlabel("Tactic")
plt.ylabel("Count")
plt.title("Tactic Distribution Across All Experiments (Stacked)")
plt.xticks(x_positions, all_tactics, rotation=45, ha='right')
plt.legend()
plt.tight_layout()
plt.show()

# %% table of tactic distribution
# should be experiment, sessionlength, and all tactics (%) as columns and a total one in the end
import numpy as np
import pandas as pd
tactic_distribution_df = pd.DataFrame(tactic_distributions)
for x in session_lengths:
    print(x['mean'])
tactic_distribution_df["session_length"] = [sl['mean'] for sl in session_lengths]
tactic_distribution_df["experiment"] = selected_experiments
tactic_distribution_df = tactic_distribution_df.set_index("experiment")
tactic_distribution_df = tactic_distribution_df.reindex(columns=["session_length"] + list(full_tactic_distributions.keys()) + ["total"])
tactic_distribution_df["total"] = tactic_distribution_df.sum(axis=1)
tactic_distribution_df = tactic_distribution_df.apply(lambda x: x / x["total"] * 100, axis=1)
tactic_distribution_df = tactic_distribution_df.round(2)
tactic_distribution_df = tactic_distribution_df.fillna(0)
tactic_distribution_df = tactic_distribution_df.fillna(0)

# create sum for session length and average for each tactic
tactic_distribution_df.loc["Total"] = tactic_distribution_df.sum(numeric_only=True)
tactic_distribution_df.loc["Total", "session_length"] = tactic_distribution_df["session_length"].mean()
tactic_distribution_df = tactic_distribution_df.round(2)
print(tactic_distribution_df)

tactic_distribution_df.to_csv(logs_path / "tactic_distribution.csv")

# %% Honeypot deceptiveness
# table of model of HP/experiment, detection, no detection, session length befor discovery and average session length
hp_deceptiveness_data = []
for i, sessions_list in enumerate(combined_sessions_list):
    honeypot_model = selected_experiments[i]
    n_experiments = len(sessions_list)

    honeypot_detected = sum(1 for session in sessions_list if session.get("discovered_honeypot") == "yes")
    honeypot_not_detected = n_experiments - honeypot_detected

    detected_percentage = honeypot_detected / n_experiments * 100
    not_detected_percentage = honeypot_not_detected / n_experiments * 100

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
        "Honeypot Model": honeypot_model,
        "Experiment": selected_experiments[i],
        "Detection Percentage": detected_percentage,
        "No Detection Percentage": not_detected_percentage,
        "Average Session Length": average_session_length,
        "Average Session Length Before Discovery": average_session_length_before_discovery,
        "Average Session Length Without Discovery": average_session_length_without_discovery
    })

hp_deceptiveness_df = pd.DataFrame(hp_deceptiveness_data)

hp_deceptiveness_df = hp_deceptiveness_df.round(2)
print(hp_deceptiveness_df)        

# %% Average session length over time (restart each configuration)
for k, sessions_list in enumerate(sessions_list_list):
    length_data = measure_session_length(combined_sessions_list[k])
    print(length_data)

    session_all_lengths = []    
    for session in sessions_list:
        print(len(session))
        if len(session) == 0:
            continue
        session_length_data = measure_session_length(session)
        session_all_lengths.append(session_length_data["session_lengths"])


    for j, session_lengths in enumerate(session_all_lengths):
        margins = []
        mus = []
        eps = 10
        eps = []

        for i in range(len(session_lengths)):
            moe = compute_confidence_interval(session_lengths[0:i], 0.05)
            margins.append(moe)
            mus.append(np.mean(session_lengths[0:i]))
            eps.append(0.4 * np.std(session_lengths[0:i], ddof=1))

        mus = np.array(mus)
        margins = np.array(margins)
        eps = np.array(eps)

        window_size = 5
        mask = (margins <= eps)
        values = np.array(range(len(mus)))

        plt.plot(values, mus, color=colors.scheme[k], label=f"Experiment {k+1}, Config {j+1}", alpha=0.7)
        plt.scatter(values[mask], mus[mask], color=colors.scheme[k], alpha=0.7)

plt.ylim(-5, 100)
plt.legend()
plt.xlabel("Sequence")
plt.ylabel("Mean")
plt.show()


# %% Average Levenshtein distance over time (restart each configuration)
for k, sessions_list in enumerate(sessions_list_list):
    combined_sessions = combined_sessions_list[k]
    
    for j, sessions in enumerate(sessions_list):
        sequence_data = measure_tactic_sequences(sessions)
        
        margins = []
        mus = []
        eps = []
        dists_list = []

        for i in range(1, len(sequence_data["indexed_sequences"])):
            # Calculate Levenshtein distances for all pairs up to index i
            current_dists = []
            for l in range(0, i):
                seq_i = sequence_data["indexed_sequences"][i]
                seq_l = sequence_data["indexed_sequences"][l]
                if seq_i and seq_l:
                    dist = editdistance.eval(seq_i, seq_l)
                    current_dists.append(dist)
                    dists_list.append(dist)
            
            if dists_list:
                eps.append(0.05 * np.std(dists_list, ddof=1) if len(dists_list) > 1 else 0)
                moe = compute_confidence_interval(np.array(dists_list), 0.05)
                margins.append(moe)
                mus.append(np.mean(dists_list))

        if mus:
            mus = np.array(mus)
            margins = np.array(margins)
            eps_threshold = eps[-1] if eps else 0
            window_size = 5
            mask = (margins <= eps_threshold) if len(margins) > window_size else np.ones(len(margins), dtype=bool)
            values = np.array(range(len(mus)))

            plt.plot(values, mus, color=colors.scheme[k], label=f"Experiment {k+1}, Config {j+1}", alpha=0.7)
            plt.plot(values[mask], mus[mask], color=colors.scheme[-1], alpha=0.7)

plt.legend()
plt.xlabel("Sequence")
plt.ylabel("Mean Levenshtein Distance")
plt.title("Average Levenshtein Distance Over Time (Restart Each Configuration)")
plt.show()

# %% Set of sequences over time
unique_session_list = []
unique_session_list_list = []
for i, comb_session in enumerate(combined_sessions_list):
    unique_session = set()
    _usll = []
    for session in comb_session:
        unique_session.add(session['tactics'])
        _usll.append(len(unique_session))
    unique_session_list.append(unique_session)
    unique_session_list_list.append(_usll)
print(unique_session_list)
print([len(sessions) for sessions in combined_sessions_list if sessions])
print([len(sessions) for sessions in unique_session_list])


plt.figure(figsize=(12, 6))
for usl in unique_session_list_list:
    plt.plot(usl, marker='o', linestyle='-')
    plt.legend([f"Experiment {i+1}" for i in range(len(unique_session_list_list))])
plt.xlabel("Session Index")
plt.ylabel("Number of Unique Sessions")
plt.title("Number of Unique Sessions Over Time")
plt.show()


# %% Average Levenshtein distance over time (no restart)
from collections import Counter
from utils import compute_confidence_interval
import editdistance
from Utils.jsun import load_json

for k, combined_sessions in enumerate(combined_sessions_list):
    sequence_data = measure_tactic_sequences(combined_sessions)

    dists = Counter()
    dists_list = []
    margins = []
    mus = []
    eps = 2
    eps = []

    for i in range(len(sequence_data["indexed_sequences"])):
        for j in range(0, i):
            seq_i = sequence_data["indexed_sequences"][i]
            seq_j = sequence_data["indexed_sequences"][j]
            if seq_i and seq_j:
                dist = editdistance.eval(seq_i, seq_j)
                dists.update([dist])
                dists_list.append(dist)
        eps.append(0.1 * np.std(dists_list, ddof=1))
        moe = compute_confidence_interval(np.array(dists_list), 0.05)
        margins.append(moe)
        mus.append(np.mean(dists_list))
    mus = np.array(mus)
    margins = np.array(margins)
    eps = np.array(eps)[-1]
    window_size = 10
    mask = (margins < eps) & (np.array([False] * window_size + [True] * (len(mus) - window_size)))
    values = np.array(range(len(mus)))

    plt.plot(values, mus, color=colors.scheme[k], label=f"Experiment {k+1}", alpha=0.7)
    
    # Add vertical bars for reconfig indices
    for reconfig_idx in reconfig_indices_list[k]:
        plt.axvline(x=reconfig_idx, color=colors.scheme[k], linestyle='--', alpha=0.5)
    
plt.xlabel("Sequence")
plt.ylabel("Mean Levenshtein Distance")
plt.xlim([50, len(mus) - 1])
plt.ylim([20, 40])
plt.legend()
plt.show()

# %% Tokens used per experiment

