from Purple.Data_analysis.metrics import measure_entropy_tactics, \
    measure_entropy_techniques, measure_entropy_session_length
from Purple.Data_analysis import colors
from Purple.Data_analysis.utils import Experiments
from typing import List

import matplotlib.pyplot as plt

def plot_entropy(experiments: Experiments, experiment_names: List[str]):
    for name, measure_function in zip(
            ["tactics", "techniques", "session_length"],
            [measure_entropy_tactics, measure_entropy_techniques, measure_entropy_session_length]
        ):
        entropy_datas = [measure_function(sessions)["entropies"] for sessions, _, _ in experiments]
        config_entropy_datas = [
            sum([list(measure_function(session)["entropies"]) for session in config_sessions], [])
            for _, config_sessions, _ in experiments
        ]
        titles = ["Entropy", "Config entropy"]
        for title, datas in zip(titles, [entropy_datas, config_entropy_datas]):
            plt.figure(figsize=(12, 6))
            for i, (entropies, (_, _, reconfig_indices), exp_name) in enumerate(
                    zip(datas, experiments, experiment_names)):
                plt.plot(entropies, marker=None, linestyle="-", c=colors.scheme[i], label=exp_name)
                plt.title(title + name)
                plt.xlabel("Session")
                plt.ylabel(f"Entropy of unique {name}")
                for index in reconfig_indices:
                    plt.axvline(index - 0.5, color=colors.scheme[i], linestyle="--", alpha=0.2)
                plt.ylim(bottom=0)
            plt.legend()