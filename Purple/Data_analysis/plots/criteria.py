from Purple.Data_analysis.metrics import measure_tactic_sequences, measure_session_length
from Purple.Data_analysis import colors
from Purple.Data_analysis.utils import Experiments, compute_confidence_interval
import matplotlib.pyplot as plt
import editdistance
import numpy as np
from typing import List

def plot_criteria(
        experiments: Experiments,
        experiment_names: List[str],
        cutoff_criterion_reconfig_list: List[bool],
        restart_configs: bool = True,
        subplot: bool = True,
        ld_alpha: float = 0.05,
        ld_eps: float = 0.2,
        sl_alpha: float = 0.05,
        sl_eps: float = 0.2,
        ):
    ld_datas = []
    ld_config_datas = []
    sl_datas = []
    sl_config_datas = []
    
    # collect data
    for (_, config_sessions, _), cutoff_criterion_reconfig in zip(experiments, cutoff_criterion_reconfig_list):
        config_tactic_sequences = [
            measure_tactic_sequences(sessions)["indexed_sequences"]
            for sessions in config_sessions
        ]
        margins = []
        mus = []
        dists_list = []
        config_margins = []
        config_mus = []
        criterion_indices = []
        cutoff_criterion_indices = []
        index_start = 0
        cutoff_index_start = 0
        for tactic_sequences in config_tactic_sequences:
            config_dists_list = []
            reconfigured = False
            broke = False
            for i in range(len(tactic_sequences)):
                for j in range(0, i):
                    seq_i = tactic_sequences[i]
                    seq_j = tactic_sequences[j]
                    if seq_i and seq_j:
                        dist = editdistance.eval(seq_i, seq_j) 
                        dists_list.append(dist)
                        config_dists_list.append(dist)
                moe = compute_confidence_interval(np.array(dists_list), ld_alpha)
                margins.append(moe)
                mus.append(np.mean(dists_list))
                config_moe = compute_confidence_interval(np.array(config_dists_list), ld_alpha)
                config_margins.append(config_moe)
                config_mus.append(np.mean(config_dists_list))

                eps = ld_eps * np.std(config_dists_list, ddof=1)
                if config_moe < eps:
                    if not reconfigured:
                        criterion_indices.append(i+index_start)
                        cutoff_criterion_indices.append(i+cutoff_index_start)
                    if cutoff_criterion_reconfig:
                        index_start += len(tactic_sequences)
                        cutoff_index_start += i + 1
                        broke = True
                        break
                    reconfigured = True
            if not broke:
                index_start += len(tactic_sequences)
                cutoff_index_start += len(tactic_sequences)
        mus = np.array(mus)
        margins = np.array(margins)
        config_mus = np.array(config_mus)
        config_margins = np.array(config_margins)

        ld_datas.append((mus, margins, criterion_indices, cutoff_criterion_indices))
        ld_config_datas.append((config_mus, config_margins, criterion_indices, cutoff_criterion_indices))

        config_session_lengths = [
            measure_session_length(sessions)["session_lengths"]
            for sessions in config_sessions
        ]
        margins = []
        mus = []
        config_margins = []
        config_mus = []
        criterion_indices = []
        cutoff_criterion_indices = []
        all_session_lengths = []
        index_start = 0
        cutoff_index_start = 0
        for session_lengths in config_session_lengths:
            broke = False
            for i in range(len(session_lengths)):
                all_session_lengths.append(session_lengths[i])
                moe = compute_confidence_interval(np.array(all_session_lengths), sl_alpha)
                margins.append(moe)
                mus.append(np.mean(all_session_lengths))

                config_moe = compute_confidence_interval(np.array(session_lengths[0:i+1]), sl_alpha)
                config_margins.append(config_moe)
                config_mus.append(np.mean(session_lengths[0:i+1]))

                eps = sl_eps * np.std(session_lengths[0:i+1], ddof=1)
                if config_moe < eps:
                    if not reconfigured:
                        criterion_indices.append(i+index_start)
                        cutoff_criterion_indices.append(i+cutoff_index_start)
                    if cutoff_criterion_reconfig:
                        index_start += len(session_lengths)
                        cutoff_index_start += i + 1
                        broke = True
                        break
                    reconfigured = True
            if not broke:
                index_start += len(session_lengths)
                cutoff_index_start += len(session_lengths)

        mus = np.array(mus)
        margins = np.array(margins)
        config_mus = np.array(config_mus)
        config_margins = np.array(config_margins)

        sl_datas.append((mus, margins, criterion_indices, cutoff_criterion_indices))
        sl_config_datas.append((config_mus, config_margins, criterion_indices, cutoff_criterion_indices))

    # plotting
    ylabels = [
        "Levenshtein distance running average",
        "Session length running average",
        "Levenshtein distance running average per config",
        "Session length running average per config",
    ]
    ylims = [(0, 100), (0, 100), (0, 100), (0, 100)]

    for datas, ylabel, ylim in zip([ld_datas, sl_datas, ld_config_datas, sl_config_datas], ylabels, ylims):
        plt.figure(figsize=(8, 6))
        n_exps = len(experiments)
        for i, (
                (mus, margins, criterion_indices, cutoff_criterion_indices),
                (_, _, reconfig_indices),
                exp_name,
                cutoff_criterion_reconfig
            ) in enumerate(zip(datas, experiments, experiment_names, cutoff_criterion_reconfig_list)):
            if subplot:
                plt.subplot(1, n_exps, 1 + i)
            if not restart_configs:
                values = np.arange(len(mus))
                lower = mus - margins
                upper = mus + margins
                plt.fill_between(values, lower, upper, alpha=0.2, color=colors.scheme[i])
                plt.plot(values, mus, color=colors.scheme[i], label=exp_name)
                if not cutoff_criterion_reconfig:
                    for index in criterion_indices:
                        plt.axvline(values[index] + 0.5, color=colors.scheme[i], alpha=0.2, linestyle=":")
                    for index in reconfig_indices:
                        plt.axvline(values[index] - 0.5, color=colors.scheme[i], alpha=0.2, linestyle="--")
                else:
                    for index in cutoff_criterion_indices:
                        plt.axvline(values[index] + 0.5, color=colors.scheme[i], alpha=0.2, linestyle=":")
            else:
                prev_index = 0
                indices = criterion_indices + [len(mus)] if cutoff_criterion_reconfig else list(reconfig_indices) + [len(mus)]
                for j, index in enumerate(indices):
                    config_mus = mus[prev_index:index]
                    config_margins = margins[prev_index:index]
                    lower = config_mus - config_margins
                    upper = config_mus + config_margins
                    values = np.arange(len(config_mus))
                    color_idx = j % len(colors.scheme)  # Use modulo to cycle through colors
                    plt.fill_between(values, lower, upper, alpha=0.2, color=colors.scheme[color_idx])
                    # Use just config number for per-config plots (plots 3 & 4)
                    if 'per config' in ylabel:
                        plt.plot(values, config_mus, color=colors.scheme[color_idx], label=f"Config {j+1}")
                    else:
                        plt.plot(values, config_mus, color=colors.scheme[color_idx], label=f"{exp_name} config {j}")
                    prev_index = index
            plt.xlabel("Session")
            plt.ylabel(ylabel)
            plt.ylim(ylim)

        if not cutoff_criterion_reconfig:
            plt.plot([],[],color=colors.black,alpha=0.2,label="Reconfiguration",linestyle="--")
        plt.plot([],[],color=colors.black,alpha=0.2,label="Criterion reconfiguration", linestyle=":")

        if subplot:
            plt.tight_layout()
            # Place legend outside the plot area to avoid covering data
            plt.figlegend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=3, fontsize=9)
        else:
            plt.legend(loc='best', fontsize=9)