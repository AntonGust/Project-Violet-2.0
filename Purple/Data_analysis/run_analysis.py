import os
import sys
from pathlib import Path
import questionary
import matplotlib.pyplot as plt
from datetime import datetime

# Add parent directory to sys.path to allow imports from project root
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from Purple.Data_analysis.utils import extract_experiment
from Purple.Data_analysis.plots import (
    plot_mitre_data,
    plot_session_length,
    plot_criteria,
    plot_entropy,
    plot_criteria_box
)


logs_path = Path(__file__).resolve().parent.parent.parent / "logs"
filter_empty_sessions = False
use_omni_sessions = False

def main():
    # List available experiments
    all_experiments = sorted(os.listdir(logs_path))
    if not all_experiments:
        print("No experiments found under", logs_path)
        sys.exit(1)

    # Select experiments to include
    selected_experiments = questionary.checkbox(
        "Select experiments to analyze:",
        choices=all_experiments
    ).ask()

    if not selected_experiments:
        print("No experiments selected, exiting.")
        sys.exit(0)

    # Optionally rename each selected experiment
    renamed_experiments = []
    for exp in selected_experiments:
        new_name = questionary.text(
            f"Enter display name for experiment '{exp}' (leave blank to keep original):"
        ).ask()
        renamed_experiments.append(new_name.strip() or exp)

    # Reorder experiments in custom sequence
    ordered_raw = []
    ordered_names = []
    ordered_names = []
    remaining = renamed_experiments.copy()
    while remaining:
        if len(remaining) > 1:
            next_exp = questionary.select(
                "Select the next experiment in the order:",
                choices=remaining
            ).ask()
        else:
            next_exp = remaining[0]
        ordered_names.append(next_exp)
        # map to display name
        idx = renamed_experiments.index(next_exp)
        ordered_raw.append(selected_experiments[idx])
        remaining.remove(next_exp)

    # Create output directory in the experiment folder
    # Use the first selected experiment as the primary output location
    output_dir = logs_path / ordered_raw[0] / "analysis_plots"
    output_dir.mkdir(exist_ok=True)
    
    # Create a timestamp for this analysis run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\nPlots will be saved to: {output_dir}")

    # Extract data for each experiment in the chosen order
    experiments = [
        extract_experiment(
            logs_path / exp_name,
            filter_empty_sessions,
            use_omni_sessions
        ) for exp_name in ordered_raw
    ]

    # Prepare plotting functions
    def prepare_plot_criteria(exps, exp_names):
        cutoff_experiments = questionary.checkbox(
            "Select experiments to apply cutoff option:",
            choices=exp_names
        ).ask()
        cutoff_list = [name in cutoff_experiments for name in exp_names]
        plot_criteria(exps, exp_names, cutoff_list)

    plot_options = {
        'Session Length': plot_session_length,
        'MITRE Distribution': plot_mitre_data,
        'Entropy': plot_entropy,
        'Criteria': prepare_plot_criteria,
        'Criteria boxplot': plot_criteria_box,
    }

    # Select plots to generate
    chosen_plots = questionary.checkbox(
        "Select plots to generate:",
        choices=list(plot_options.keys())
    ).ask()

    if not chosen_plots:
        print("No plots selected, exiting.")
        sys.exit(0)

    # Generate and save plots with reordered labels
    for plot_name in chosen_plots:
        print(f"\nGenerating plot: {plot_name}")
        plot_func = plot_options[plot_name]
        # Pass ordered display names for labeling
        plot_func(experiments, ordered_names)
        
        # Save all open figures
        figs = [plt.figure(n) for n in plt.get_fignums()]
        for i, fig in enumerate(figs):
            # Create a clean filename
            clean_name = plot_name.lower().replace(' ', '_')
            if len(figs) > 1:
                filename = f"{clean_name}_{i+1}_{timestamp}.png"
            else:
                filename = f"{clean_name}_{timestamp}.png"
            
            filepath = output_dir / filename
            fig.savefig(filepath, dpi=300, bbox_inches='tight')
            print(f"  Saved: {filename}")
        
        plt.close('all')  # Close all figures after saving
    
    print(f"\nAll plots saved to: {output_dir}")

if __name__ == "__main__":
    main()
