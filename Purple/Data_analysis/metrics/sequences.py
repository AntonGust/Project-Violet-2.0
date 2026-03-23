import editdistance
import numpy as np
from typing import Dict, List, Any, Literal
from Purple.Data_analysis.utils import Sessions, compute_confidence_interval

def measure_tactic_sequences(sessions: Sessions) -> Dict[str, Any]:
    return measure_sequences(sessions, "tactic")

def measure_technique_sequences(sessions: Sessions) -> Dict[str, Any]:
    return measure_sequences(sessions, "technique")

def measure_command_sequences(sessions: Sessions) -> Dict[str, Any]:
    return measure_sequences(sessions, "command")

def measure_sequences(sessions: Sessions,
        t_name: Literal["tactic", "technique", "command"]) -> Dict[str, Any]:
    t_to_index: Dict[str, int] = {}
    sequences: List[List[str]] = []
    indexed_sequences: List[List[int]] = []

    for session in sessions:
        seq = []
        for command in session.get("full_session", []):
            t = command.get(t_name, "")
            if t_name == "command":
                t = t.split(" ")[0]
            seq.append(t)
            if t not in t_to_index:
                t_to_index[t] = len(t_to_index)
        indexed_seq = [t_to_index[t] for t in seq]
        
        sequences.append(seq)
        indexed_sequences.append(indexed_seq)

    results = {
        f"{t_name}": t_to_index,
        "sequences": sequences,
        "indexed_sequences": indexed_sequences,
    }

    return results
