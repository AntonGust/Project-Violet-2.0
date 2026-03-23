import numpy as np
from typing import Dict, Any
from Purple.utils import Sessions
from collections import Counter

def measure_session_length(sessions: Sessions, remove_zeros: bool = False) -> Dict[str, Any]:
    session_lengths = [session.get("length", 0) for session in sessions]
    if remove_zeros:
        session_lengths = np.array([length for length in session_lengths if length > 0])
    else:
        session_lengths = np.array(session_lengths)

    if len(session_lengths) == 0 or (remove_zeros and len(session_lengths) == 0):
        return {
            "mean": 0.0, "var": 0.0, "std": 0.0,
            "min": 0.0, "max": 0.0, "range": 0.0,
            "median": 0.0, "q1": 0.0, "q3": 0.0,
            "middle_range": 0.0,
            "five_most_common": [],
            "session_lengths": session_lengths,
        }

    mean_length = session_lengths.mean()
    var_length = session_lengths.var(ddof=1)
    std_length = session_lengths.std(ddof=1)
    min_length = session_lengths.min()
    max_length = session_lengths.max()
    range_length = max_length - min_length
    q1 = np.percentile(session_lengths, 25)
    median_length = np.percentile(session_lengths, 50)
    q3 = np.percentile(session_lengths, 75)

    length_counts = Counter(session_lengths)
    five_most_common = length_counts.most_common(5)

    results = {
        "mean": mean_length,
        "var": var_length,
        "std": std_length,
        "min": min_length,
        "max": max_length,
        "range": range_length,
        "median": median_length,
        "q1": q1,
        "q3": q3,
        "middle_range": q3 - q1,
        "five_most_common": five_most_common,
    }
    results = {
        key:float(value) if key != "five_most_common" else [(int(pair[0]), pair[1]) for pair in value]
        for key, value in results.items()
    }
    results["session_lengths"] = session_lengths
    return results
