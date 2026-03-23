from Purple.Data_analysis.metrics import measure_mitre_distribution
from Purple.Data_analysis import colors
from Purple.Data_analysis.utils import Experiments
import matplotlib.pyplot as plt
from typing import List, Optional

def plot_mitre_data(
        experiments: Experiments,
        experiment_names: List[str],
        reconfig_interval: Optional[int] = 100):
    mitre_dist_datas = [measure_mitre_distribution(sessions) for sessions,_,_ in experiments]

    for name in ["tactics", "techniques"]:
        for plot_data_name in [
                f"session_cum_num_{name}",
                f"session_num_{name}",
            ]:
            plt.figure(figsize=(12, 6))
            for i, (mitre_dist_data, (_, _, reconfig_indices), exp_name) in enumerate(
                    zip(mitre_dist_datas, experiments, experiment_names)):
                plt.plot(
                    mitre_dist_data[plot_data_name],
                    marker="o",
                    markersize=2,
                    linestyle="-",
                    c=colors.scheme[i],
                    label=exp_name)
                plt.xlabel("Session")
                plt.ylabel(f"Number of unique {name}")
                if reconfig_interval is None:
                    for index in reconfig_indices:
                        plt.axvline(index - 0.5, color=colors.scheme[i], linestyle="--", alpha=0.2)
                else:
                    max_length = max([len(sessions) for (sessions, _, _) in experiments])
                    for j in range(reconfig_interval, max_length-1, reconfig_interval):
                        plt.axvline(j - 0.5, color=colors.black, linestyle="--", alpha=0.2)
            plt.plot([],[],color=colors.black, linestyle="--", label="Reconfiguration")
            plt.legend()
