from Purple.Data_analysis.metrics import measure_session_length
from Purple.Data_analysis import colors
from Purple.Data_analysis.utils import Experiments, compute_confidence_interval
import matplotlib.pyplot as plt
import numpy as np
from typing import List

def plot_criteria_box(
        experiments: Experiments,
        experiment_names: List[str],
        sl_alpha: float = 0.05,
        sl_eps: float = 0.2,
        ):
    sl_datas = []
    no_reconfig_experiments = []
    ymax = 0
    for sessions, config_sessions, _  in experiments:
        no_reconfig_experiments.append(len(config_sessions) <= 1)

        all_session_lengths = measure_session_length(sessions, True)["session_lengths"]
        ymax = max(ymax, max(all_session_lengths))
        config_session_lengths = [
            measure_session_length(s, True)["session_lengths"]
            for s in config_sessions
        ]
        all_moe = compute_confidence_interval(np.array(all_session_lengths), sl_alpha)
        all_mu = np.mean(all_session_lengths)
        criterion_mus = []
        criterion_moes = []
        criterion_stds = []
        criterion_reconfig_indices = []
        config_mus = []
        config_moes = []
        config_stds = []
        for session_lengths in config_session_lengths:
            criterion_reconfig_index = None
            criterion_moe = None
            criterion_mu = None
            criterion_std = None
            for i in range(len(session_lengths)):
                criterion_mu = np.mean(session_lengths[0:i+1])
                criterion_moe = compute_confidence_interval(np.array(session_lengths[0:i+1]), sl_alpha)
                criterion_std = np.std(session_lengths[0:i+1], ddof=1)
                eps = sl_eps * criterion_std
                if criterion_moe < eps:
                    criterion_reconfig_index = i
            if not (criterion_reconfig_index is None):
                criterion_mus.append(criterion_mu)
                criterion_moes.append(criterion_moe)
                criterion_stds.append(criterion_std)
                criterion_reconfig_indices.append(criterion_reconfig_index)
            config_mu = np.mean(session_lengths)
            config_moe = compute_confidence_interval(np.array(session_lengths), sl_alpha)
            config_std = np.std(session_lengths, ddof=1)
            config_mus.append(config_mu)
            config_moes.append(config_moe)
            config_stds.append(config_std)

        sl_datas.append((
            all_mu,
            all_moe,
            np.array(config_mus), 
            np.array(config_moes),
            np.array(config_stds),
            np.array(criterion_mus),
            np.array(criterion_moes),
            np.array(criterion_stds),
            config_session_lengths
        ))

    widths = [len(cfg_mus) + 1 for (_, _, cfg_mus, *_) in sl_datas]
    n = len(sl_datas)
    fig, axes = plt.subplots(
        1, n,
        figsize=(sum(widths) * 1, 4),       # you can adjust the 0.5 scale factor
        gridspec_kw={'width_ratios': widths}
    )
    # Ensure axes is always iterable (handle single subplot case)
    if n == 1:
        axes = [axes]
    for i, (
            (
                all_mu, 
                all_moe,
                config_mus,
                config_moes, 
                config_stds,
                criterion_mus,
                criterion_moes,
                criterion_stds,
                config_session_lengths
            ),
            exp_name,
            no_reconfig
        ) in enumerate(zip(sl_datas, experiment_names, no_reconfig_experiments)):
        xticks = np.arange(len(config_mus)) + 1
        ax = axes[i]
        ax.set_ylim(-5, ymax + 5)
        ax.set_title(exp_name, fontsize=10)

        sorted_list = sorted(zip(config_session_lengths, xticks), key=lambda x: np.mean(x[0]))
        sorted_session_lengths, sorted_xticks = zip(*list(sorted_list))

        # your boxplot on config_session_lengths
        c = colors.scheme[i]
        ax.boxplot(
            sorted_session_lengths,
            patch_artist=True,  
            boxprops=dict(facecolor=c), 
            medianprops=dict(color='k'),  
            whiskerprops=dict(color=c), 
            capprops=dict(color=c), 
            flierprops=dict(markeredgecolor=c),
            labels=sorted_xticks
        )
        ax.set_xlabel("Configuration")
        if i == 0:
            ax.set_ylabel("Session length")
    plt.tight_layout()
    plt.figure()
    for i, (
            (
                all_mu, 
                all_moe,
                config_mus,
                config_moes, 
                config_stds,
                criterion_mus,
                criterion_moes,
                criterion_stds,
                config_session_lengths
            ),
            exp_name,
            no_reconfig
        ) in enumerate(zip(sl_datas, experiment_names, no_reconfig_experiments)):
        if no_reconfig:
            plt.axhline(all_mu, color=colors.scheme[i], label=exp_name)
            plt.axhspan(all_mu - all_moe, all_mu + all_moe, alpha=0.2, color=colors.scheme[i])
            continue
        values = np.arange(len(config_mus)) + 1
        plt.errorbar(
            values,
            config_mus,
            yerr=config_moes,
            fmt='o:',
            color=colors.scheme[i],
            capsize=10,
            label=exp_name
        )
        plt.xlabel("Configuration")
        plt.ylabel("Sample mean of session length (with 95% confidence interval)")
    plt.legend()
    plt.tight_layout()