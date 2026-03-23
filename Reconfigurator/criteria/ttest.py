import editdistance
import numpy as np
from scipy.stats import t
from typing import List, Dict, Any
from Reconfigurator.criteria.abstract import AbstractReconfigCriterion
from Purple.Data_analysis.metrics import measure_tactic_sequences

def compute_confidence_interval(session_lengths: np.ndarray, alpha: float) -> float:
    s = session_lengths.std(ddof=1)
    n = session_lengths.shape[0]

    t_crit = t.ppf(1 - alpha/2, df=n - 1)
    moe = t_crit * (s / np.sqrt(n))

    return float(moe)

VARIABLES = ["session_length", "tactic_sequences"]

class TTestReconfigCriterion(AbstractReconfigCriterion):
    def __init__(self, variable: str, tolerance: float, 
            confidence_level: float):
        assert variable in VARIABLES, f"Variable '{variable}' is not supported. Supported variables: {VARIABLES}"
        self.variable = variable
        self.tolerance = tolerance
        assert 0 < confidence_level < 1, f"Confidence level {self.confidence_level} is not in the range (0,1)"
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level
        super().__init__()

    def reset(self):
        self.session_lengths: List[float] = []
        self.sessions: List[Dict[str, Any]]
        self.moes: List[float] = []
        self.eps: List[float] = []

    def update(self, session):
        match self.variable:
            case "session_length":
                self.session_lengths.append(int(session.get("length")))
                self.moes.append(
                    compute_confidence_interval(
                        np.array(self.session_lengths),
                        self.alpha
                    )
                )
                self.eps.append(self.tolerance * np.std(self.session_lengths, ddof=1))
            case "tactic_sequences":
                tactic_sequence_data = measure_tactic_sequences([session])
                dists_list = []
                for i in range(len(tactic_sequence_data["indexed_sequences"])):
                    for j in range(0, i):
                        seq_i = tactic_sequence_data["indexed_sequences"][i]
                        seq_j = tactic_sequence_data["indexed_sequences"][j]
                        if seq_i and seq_j:
                            dist = editdistance.eval(seq_i, seq_j)
                            dists_list.append(dist)
                if dists_list:
                    self.moes.append(
                        compute_confidence_interval(
                            np.array(dists_list),
                            self.alpha
                        )
                    )
                    self.eps.append(self.tolerance * np.std(dists_list, ddof=1))
        
    def should_reconfigure(self):
        if not self.moes:
            return False
        return self.moes[-1] < self.eps[-1]