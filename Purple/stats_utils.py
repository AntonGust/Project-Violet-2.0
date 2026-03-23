import numpy as np
from typing import Dict, List, Tuple, Any, Union


def calculate_basic_stats(data: np.ndarray) -> Dict[str, float]:
    return {
        'mean': float(data.mean()),
        'var': float(data.var()),
        'std': float(data.std()),
        'min': float(data.min()),
        'max': float(data.max()),
        'range': float(data.max() - data.min()),
    }


def calculate_quartiles(data: np.ndarray) -> Dict[str, float]:
    q1 = float(np.percentile(data, 25))
    median = float(np.percentile(data, 50))
    q3 = float(np.percentile(data, 75))
    return {
        'q1': q1,
        'median': median,
        'q3': q3,
        'iqr': float(q3 - q1),
    }


def calculate_percentiles(
    data: np.ndarray, percentiles: List[int]
) -> Dict[str, float]:
    return {
        f'p{p}': float(np.percentile(data, p)) for p in percentiles
    }


def detect_outliers_iqr(
    data: np.ndarray, multiplier: float = 1.5
) -> Tuple[list, Dict[str, float]]:
    q1 = float(np.percentile(data, 25))
    q3 = float(np.percentile(data, 75))
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr

    outliers = [float(x) for x in data if x < lower or x > upper]

    thresholds = {
        'lower': float(lower),
        'upper': float(upper),
        'q1': q1,
        'q3': q3,
        'iqr': float(iqr),
    }
    return outliers, thresholds


def detect_outliers_std(
    data: np.ndarray,
    std_multiplier: float = 2.0,
    method: str = 'both',
) -> Tuple[list, Dict[str, float]]:
    if method not in ('both', 'above', 'below'):
        raise ValueError(f"Invalid method '{method}'. Must be 'both', 'above', or 'below'.")

    mean = float(data.mean())
    std = float(data.std())
    lower = mean - std_multiplier * std
    upper = mean + std_multiplier * std

    if method == 'both':
        outliers = [float(x) for x in data if x < lower or x > upper]
    elif method == 'above':
        outliers = [float(x) for x in data if x > upper]
    else:  # below
        outliers = [float(x) for x in data if x < lower]

    thresholds = {
        'mean': mean,
        'std': std,
        'lower': float(lower),
        'upper': float(upper),
    }
    return outliers, thresholds


def detect_outliers_zscore(
    data: np.ndarray, threshold: float = 3.0
) -> Tuple[List[Tuple[int, float, float]], Dict[str, float]]:
    mean = float(data.mean())
    std = float(data.std())

    stats = {'mean': mean, 'std': std, 'threshold': float(threshold)}

    if std == 0.0:
        return [], stats

    z_scores = (data - mean) / std
    outliers = [
        (int(i), float(data[i]), float(z_scores[i]))
        for i in range(len(data))
        if abs(z_scores[i]) > threshold
    ]
    return outliers, stats


def summarize_distribution(data: np.ndarray) -> Dict[str, Any]:
    return {
        'basic': calculate_basic_stats(data),
        'quartiles': calculate_quartiles(data),
        'n': int(len(data)),
        'n_unique': int(len(np.unique(data))),
    }


def compare_distributions(
    group1: np.ndarray,
    group2: np.ndarray,
    labels: Tuple[str, str] = ('Group 1', 'Group 2'),
) -> Dict[str, Any]:
    summary1 = summarize_distribution(group1)
    summary2 = summarize_distribution(group2)

    return {
        labels[0]: summary1,
        labels[1]: summary2,
        'difference': {
            'mean_diff': float(summary1['basic']['mean'] - summary2['basic']['mean']),
            'median_diff': float(summary1['quartiles']['median'] - summary2['quartiles']['median']),
            'std_diff': float(summary1['basic']['std'] - summary2['basic']['std']),
        },
    }


def normalize_data(
    data: np.ndarray, method: str = 'zscore'
) -> Tuple[np.ndarray, Dict[str, Any]]:
    if method == 'zscore':
        mean = float(data.mean())
        std = float(data.std(ddof=1))
        if std == 0.0:
            normalized = np.zeros_like(data, dtype=float)
        else:
            normalized = (data - mean) / std
        params = {'mean': mean, 'std': std, 'method': 'zscore'}

    elif method == 'minmax':
        mn = float(data.min())
        mx = float(data.max())
        if mn == mx:
            normalized = np.zeros_like(data, dtype=float)
        else:
            normalized = (data - mn) / (mx - mn)
        params = {'min': mn, 'max': mx, 'method': 'minmax'}

    elif method == 'robust':
        median = float(np.median(data))
        q1 = float(np.percentile(data, 25))
        q3 = float(np.percentile(data, 75))
        iqr = q3 - q1
        if iqr == 0.0:
            normalized = np.zeros_like(data, dtype=float)
        else:
            normalized = (data - median) / iqr
        params = {'median': median, 'iqr': float(iqr), 'method': 'robust'}

    else:
        raise ValueError(f"Invalid method '{method}'. Must be 'zscore', 'minmax', or 'robust'.")

    return normalized.astype(float), params
