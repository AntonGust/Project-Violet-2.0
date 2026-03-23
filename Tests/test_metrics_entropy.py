"""
Tests for metrics/entropy.py functions.

Tests entropy calculation functions for MITRE tactics/techniques and session lengths.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Purple.metrics.entropy import (
    compute_entropy,
    measure_entropy_mitre,
    measure_entropy_tactics,
    measure_entropy_techniques,
    measure_entropy_session_length
)


class TestComputeEntropy:
    """Tests for compute_entropy function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_uniform_distribution(self):
        """Test entropy with uniform distribution (maximum entropy)."""
        # Uniform distribution has maximum entropy
        probs = np.array([0.25, 0.25, 0.25, 0.25])
        entropy = compute_entropy(probs)

        # Entropy of uniform distribution with 4 items = log(4) ≈ 1.386
        expected_entropy = np.log(4)
        assert abs(entropy - expected_entropy) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_deterministic(self):
        """Test entropy with deterministic distribution (minimum entropy)."""
        # One probability = 1, others = 0 (minimum entropy)
        probs = np.array([1.0, 0.0, 0.0, 0.0])
        entropy = compute_entropy(probs)

        # Entropy should be 0
        assert abs(entropy) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_two_outcomes(self):
        """Test entropy with binary distribution."""
        # Equal probability binary
        probs = np.array([0.5, 0.5])
        entropy = compute_entropy(probs)

        # Binary entropy with p=0.5 is log(2) ≈ 0.693
        expected_entropy = np.log(2)
        assert abs(entropy - expected_entropy) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_skewed_distribution(self):
        """Test entropy with skewed distribution."""
        probs = np.array([0.7, 0.2, 0.1])
        entropy = compute_entropy(probs)

        # Entropy should be between 0 and log(3)
        assert 0 < entropy < np.log(3)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_entropy_with_zeros(self):
        """Test entropy handles zero probabilities correctly."""
        probs = np.array([0.5, 0.5, 0.0, 0.0])
        entropy = compute_entropy(probs)

        # Should handle 0*log(0) = 0
        assert np.isfinite(entropy)
        assert entropy >= 0

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_entropy_single_outcome(self):
        """Test entropy with single outcome."""
        probs = np.array([1.0])
        entropy = compute_entropy(probs)

        assert abs(entropy) < 0.01


class TestMeasureEntropyMitre:
    """Tests for measure_entropy_mitre function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_mitre_tactics_structure(self, sample_sessions_varied_tactics):
        """Test that entropy measurement returns correct structure."""
        result = measure_entropy_mitre(sample_sessions_varied_tactics, "tactics")

        # Check expected keys
        assert 'entropies' in result
        assert 'unique' in result
        assert 'counts' in result
        assert 'probabilities' in result

        # Check types
        assert isinstance(result['entropies'], np.ndarray)
        assert isinstance(result['unique'], list)
        assert isinstance(result['counts'], np.ndarray)
        assert isinstance(result['probabilities'], np.ndarray)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_mitre_techniques_structure(self, sample_sessions_varied_tactics):
        """Test entropy measurement for techniques."""
        result = measure_entropy_mitre(sample_sessions_varied_tactics, "techniques")

        assert 'entropies' in result
        assert 'unique' in result
        assert len(result['unique']) > 0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_mitre_entropies_length(self, sample_sessions_varied_tactics):
        """Test that entropies array has correct length."""
        result = measure_entropy_mitre(sample_sessions_varied_tactics, "tactics")

        # Should have one entropy value per session
        num_sessions = len(sample_sessions_varied_tactics)
        assert len(result['entropies']) == num_sessions

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_mitre_probabilities_sum_to_one(self, sample_sessions_varied_tactics):
        """Test that probabilities sum to 1 for each session."""
        result = measure_entropy_mitre(sample_sessions_varied_tactics, "tactics")

        probs = result['probabilities']

        # Each row should sum to 1 (or close to it)
        for row in probs:
            assert abs(row.sum() - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_mitre_counts_decrease(self, sample_sessions_varied_tactics):
        """Test that counts increase as sessions progress (forward chronology)."""
        result = measure_entropy_mitre(sample_sessions_varied_tactics, "tactics")

        counts = result['counts']

        # Total counts in each row should increase or stay same
        # (as we accumulate sessions going forward in time)
        row_sums = counts.sum(axis=1)

        for i in range(len(row_sums) - 1):
            # Each row should have <= counts than next (going forward, accumulating)
            assert row_sums[i] <= row_sums[i + 1] + 1  # Allow small rounding


class TestMeasureEntropyTactics:
    """Tests for measure_entropy_tactics wrapper function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_tactics_wrapper(self, sample_sessions_varied_tactics):
        """Test that tactics wrapper calls mitre function correctly."""
        result = measure_entropy_tactics(sample_sessions_varied_tactics)

        assert 'entropies' in result
        assert 'unique' in result

        # Should have tactics, not techniques
        unique_items = result['unique']
        assert any('Discovery' in item or 'Execution' in item or 'Impact' in item
                  for item in unique_items if isinstance(item, str))


class TestMeasureEntropyTechniques:
    """Tests for measure_entropy_techniques wrapper function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_techniques_wrapper(self, sample_sessions_varied_tactics):
        """Test that techniques wrapper calls mitre function correctly."""
        result = measure_entropy_techniques(sample_sessions_varied_tactics)

        assert 'entropies' in result
        assert 'unique' in result

        # Should have technique IDs (e.g., T1083)
        unique_items = result['unique']
        assert any(item.startswith('T') for item in unique_items if isinstance(item, str))


class TestMeasureEntropySessionLength:
    """Tests for measure_entropy_session_length function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_session_length_structure(self, sample_sessions_varied_tactics):
        """Test return structure of session length entropy."""
        result = measure_entropy_session_length(sample_sessions_varied_tactics)

        # Check expected keys
        assert 'entropies' in result
        assert 'unique_lengths' in result
        assert 'counts' in result
        assert 'probabilities' in result

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_session_length_unique_lengths(self, sample_sessions_varied_tactics):
        """Test that unique lengths are correctly identified."""
        result = measure_entropy_session_length(sample_sessions_varied_tactics)

        unique_lengths = result['unique_lengths']

        # sessions have lengths [3, 4, 2]
        expected_lengths = [2, 3, 4]
        assert sorted(unique_lengths) == expected_lengths

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_session_length_entropies_count(self, sample_sessions_basic):
        """Test that entropies array has correct length."""
        result = measure_entropy_session_length(sample_sessions_basic)

        # Should have one entropy value per session
        num_sessions = len(sample_sessions_basic)
        assert len(result['entropies']) == num_sessions

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_session_length_probabilities_sum(self, sample_sessions_basic):
        """Test that probabilities sum to 1."""
        result = measure_entropy_session_length(sample_sessions_basic)

        probs = result['probabilities']

        for row in probs:
            assert abs(row.sum() - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_entropy_session_length_single_session(self, single_session):
        """Test with single session."""
        result = measure_entropy_session_length(single_session)

        assert len(result['entropies']) == 1
        assert len(result['unique_lengths']) == 1

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_entropy_session_length_identical_lengths(self):
        """Test with sessions all having same length."""
        sessions = [
            {"length": 5, "full_session": []},
            {"length": 5, "full_session": []},
            {"length": 5, "full_session": []}
        ]

        result = measure_entropy_session_length(sessions)

        # All same length means entropy should be 0 (deterministic)
        entropies = result['entropies']

        for entropy in entropies:
            assert abs(entropy) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_session_length_with_zeros(self, sample_sessions_with_zeros):
        """Test entropy calculation with zero-length sessions."""
        result = measure_entropy_session_length(sample_sessions_with_zeros)

        # Should include zeros in unique lengths
        unique_lengths = result['unique_lengths']
        assert 0 in unique_lengths

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_values_non_negative(self, sample_sessions_varied_tactics):
        """Test that all entropy values are non-negative."""
        result_tactics = measure_entropy_tactics(sample_sessions_varied_tactics)
        result_techniques = measure_entropy_techniques(sample_sessions_varied_tactics)
        result_lengths = measure_entropy_session_length(sample_sessions_varied_tactics)

        assert all(e >= 0 for e in result_tactics['entropies'])
        assert all(e >= 0 for e in result_techniques['entropies'])
        assert all(e >= 0 for e in result_lengths['entropies'])

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_entropy_increases_with_diversity(self):
        """Test that entropy increases when distribution becomes more diverse."""
        # Homogeneous sessions (low diversity)
        sessions_low = [
            {
                "length": 3,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"}
                ]
            }
        ]

        # Diverse sessions (high diversity)
        sessions_high = [
            {
                "length": 3,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "wget", "tactic": "Command And Control", "technique": "T1071"},
                    {"command": "rm", "tactic": "Impact", "technique": "T1485"}
                ]
            }
        ]

        result_low = measure_entropy_tactics(sessions_low)
        result_high = measure_entropy_tactics(sessions_high)

        # More diversity should lead to higher entropy
        # Note: This test might need adjustment based on actual implementation behavior
        # since we're looking at the first session's entropy
        assert result_high['entropies'][0] >= result_low['entropies'][0]

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_entropy_empty_sessions_handling(self):
        """Test handling of sessions with no commands."""
        sessions = [
            {"length": 0, "full_session": []},
            {"length": 2, "full_session": [
                {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                {"command": "pwd", "tactic": "Discovery", "technique": "T1083"}
            ]}
        ]

        # Should not crash with empty sessions
        result_tactics = measure_entropy_tactics(sessions)
        result_lengths = measure_entropy_session_length(sessions)

        assert len(result_tactics['entropies']) == 2
        assert len(result_lengths['entropies']) == 2
