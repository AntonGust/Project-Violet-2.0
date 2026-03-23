import os
from pathlib import Path
import numpy as np
from typing import List, Dict, Any, Tuple, Union
from scipy.stats import t

Session = Dict[str, Any]
Sessions = List[Session]
ConfigSessions = List[Sessions]
ReconfigIndices = List[int]
Experiment = Tuple[Sessions, ConfigSessions, ReconfigIndices]
Experiments = List[Experiment]


def compute_confidence_interval(
    data: np.ndarray,
    alpha: float,
    return_bounds: bool = False,
) -> Union[float, Tuple[float, float]]:
    s = data.std(ddof=1)
    n = data.shape[0]
    t_crit = t.ppf(1 - alpha / 2, df=n - 1)
    moe = t_crit * (s / np.sqrt(n))

    if return_bounds:
        mean = float(data.mean())
        return (float(mean - moe), float(mean + moe))
    return float(moe)
