import config
import datetime
import os
import json

from Reconfigurator.criteria import EntropyReconfigCriterion, BasicReconfigCriterion, \
     NeverReconfigCriterion, TTestReconfigCriterion
from Sangria.model import ReconfigCriteria

def create_experiment_folder(experiment_name=None):
    # timestamp = datetime.datetime.now().isoformat()[:-7]
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H_%M_%S")

    folder_name = f"experiment_{timestamp}"
    if experiment_name:
        folder_name = f"{experiment_name}_{timestamp}"

    # create the logs folder if it doesn't exist
    path = "logs/" + folder_name

    os.makedirs("logs", exist_ok=True)
    os.makedirs(path, exist_ok=True)

    metadata = create_metadata()
    metadata_path = os.path.join(path, "metadata.json")

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
        print(f"Metadata saved to {metadata_path}")

    return path

def create_metadata():
    md = {
        "llm_model_sangria": config.llm_model_sangria,
        "llm_model_reconfig": config.llm_model_reconfig,
        "llm_model_honeypot": config.llm_model_honeypot,
        "initial_profile": config.initial_profile,
        "simulate_command_line": config.simulate_command_line,
        "num_of_sessions": config.num_of_sessions,
        "max_session_length": config.max_session_length,
        "reconfig_method": config.reconfig_method,
        "reconfig": {
            "ba_interval": config.ba_interval,
            "en_variable": config.en_variable,
            "en_window_size": config.en_window_size,
            "en_tolerance": config.en_tolerance,
            "tt_variable": config.tt_variable,
            "tt_tolerance": config.tt_tolerance,
            "tt_confidence": config.tt_confidence,
        }
    }

    return md

def select_reconfigurator():
    match config.reconfig_method:
        case ReconfigCriteria.NO_RECONFIG:
            reconfigurator = NeverReconfigCriterion()
        case ReconfigCriteria.BASIC:
            reconfigurator = BasicReconfigCriterion(
                    config.ba_interval)
        case ReconfigCriteria.ENTROPY:
            reconfigurator = EntropyReconfigCriterion(
                    config.en_variable,
                    config.en_tolerance,
                    config.en_window_size)
        case ReconfigCriteria.T_TEST:
                reconfigurator = TTestReconfigCriterion(
                    config.tt_variable,
                    config.tt_tolerance,
                    config.tt_confidence)
        case _:
            raise ValueError(f"The reconfiguration criterion {config.reconfig_method} is not supported.")
        
    return reconfigurator
