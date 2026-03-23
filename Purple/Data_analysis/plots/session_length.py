from Purple.Data_analysis.metrics import measure_session_length
from Purple.Data_analysis import colors
from Purple.Data_analysis.utils import Experiments
from typing import List

import matplotlib.pyplot as plt

def plot_session_length(
        experiments: Experiments,
        experiment_names: List[str],
        subplot: bool = True):
    length_datas = [measure_session_length(sessions) for sessions, _, _ in experiments]

    plt.figure(figsize=(12, 6))
    n_exps = len(experiments)
    for i, (length_data, (_, _, reconfig_indices), exp_name) in enumerate(
            zip(length_datas, experiments, experiment_names)):
        if subplot:
            plt.subplot(1, n_exps, i + 1)
        plt.xlabel("Session")
        plt.ylabel("Number of commands")
        plt.plot(length_data["session_lengths"], color=colors.scheme[i], label=exp_name)
        for index in reconfig_indices:
            plt.axvline(index - 0.5, color=colors.scheme[i], linestyle="--", alpha=0.2)
    plt.figlegend()
    plt.tight_layout()
