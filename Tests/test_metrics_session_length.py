"""
Tests for metrics/session_length.py functions.

Tests the measure_session_length function with various session configurations.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Purple.metrics.session_length import measure_session_length


class TestMeasureSessionLength:
    """Tests for measure_session_length function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_basic_session_statistics(self, sample_sessions_basic):
        """Test basic session length statistics."""
        result = measure_session_length(sample_sessions_basic)

        # Check all expected keys are present
        expected_keys = ['mean', 'var', 'std', 'min', 'max', 'range',
                        'median', 'q1', 'q3', 'middle_range',
                        'five_most_common', 'session_lengths']

        for key in expected_keys:
            assert key in result

        # Check value types
        assert isinstance(result['mean'], float)
        assert isinstance(result['var'], float)
        assert isinstance(result['std'], float)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_session_lengths_extracted(self, sample_sessions_basic):
        """Test that session lengths are correctly extracted."""
        result = measure_session_length(sample_sessions_basic)

        session_lengths = result['session_lengths']
        expected_lengths = [5, 3, 4]

        assert len(session_lengths) == 3
        assert list(session_lengths) == expected_lengths

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mean_calculation(self, sample_sessions_basic):
        """Test mean calculation is correct."""
        result = measure_session_length(sample_sessions_basic)

        # Expected mean: (5 + 3 + 4) / 3 = 4.0
        assert abs(result['mean'] - 4.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_min_max_range(self, sample_sessions_basic):
        """Test min, max, and range calculations."""
        result = measure_session_length(sample_sessions_basic)

        assert result['min'] == 3.0
        assert result['max'] == 5.0
        assert result['range'] == 2.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_median_calculation(self, sample_sessions_basic):
        """Test median calculation."""
        result = measure_session_length(sample_sessions_basic)

        # For lengths [3, 4, 5], median is 4
        assert result['median'] == 4.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_quartiles_calculation(self, sample_sessions_basic):
        """Test quartile calculations."""
        result = measure_session_length(sample_sessions_basic)

        assert 'q1' in result
        assert 'q3' in result
        assert result['q1'] <= result['median'] <= result['q3']

        # middle_range should be IQR
        assert result['middle_range'] == result['q3'] - result['q1']

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_five_most_common(self, sample_sessions_basic):
        """Test most common lengths tracking."""
        result = measure_session_length(sample_sessions_basic)

        five_most_common = result['five_most_common']

        assert isinstance(five_most_common, list)
        assert len(five_most_common) <= 5

        # Each item should be (length, count)
        for length, count in five_most_common:
            assert isinstance(length, int)
            assert isinstance(count, int)
            assert count > 0

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_remove_zeros_false(self, sample_sessions_with_zeros):
        """Test with remove_zeros=False includes zero-length sessions."""
        result = measure_session_length(sample_sessions_with_zeros, remove_zeros=False)

        # Should include all sessions including zeros: [5, 0, 3, 0, 7]
        session_lengths = result['session_lengths']
        assert len(session_lengths) == 5

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_remove_zeros_true(self, sample_sessions_with_zeros):
        """Test with remove_zeros=True filters out zero-length sessions."""
        result = measure_session_length(sample_sessions_with_zeros, remove_zeros=True)

        # Should only have non-zero lengths: [5, 3, 7]
        session_lengths = result['session_lengths']
        assert all(length > 0 for length in session_lengths)
        assert len(session_lengths) == 3

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_single_session(self, single_session):
        """Test with a single session."""
        result = measure_session_length(single_session)

        assert result['mean'] == 2.0
        assert result['min'] == 2.0
        assert result['max'] == 2.0
        assert result['range'] == 0.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_identical_lengths(self):
        """Test with sessions that all have the same length."""
        sessions = [
            {"length": 5, "full_session": []},
            {"length": 5, "full_session": []},
            {"length": 5, "full_session": []}
        ]

        result = measure_session_length(sessions)

        assert result['mean'] == 5.0
        assert result['var'] == 0.0
        assert result['std'] == 0.0
        assert result['range'] == 0.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_variance_std_calculation(self):
        """Test variance and standard deviation calculations."""
        sessions = [
            {"length": 1, "full_session": []},
            {"length": 2, "full_session": []},
            {"length": 3, "full_session": []}
        ]

        result = measure_session_length(sessions)

        # For [1, 2, 3]: mean=2, var=1, std=1
        assert abs(result['mean'] - 2.0) < 0.01
        assert abs(result['var'] - 1.0) < 0.01
        assert abs(result['std'] - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_large_session_set(self):
        """Test with a larger set of sessions."""
        # Create 100 sessions with varying lengths
        sessions = [{"length": i % 20 + 1, "full_session": []} for i in range(100)]

        result = measure_session_length(sessions)

        assert len(result['session_lengths']) == 100
        assert result['min'] > 0
        assert result['max'] <= 21
        assert len(result['five_most_common']) <= 5

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_missing_length_field(self):
        """Test with sessions missing the 'length' field."""
        sessions = [
            {"full_session": []},
            {"full_session": []},
            {"length": 5, "full_session": []}
        ]

        # Without remove_zeros, missing lengths default to 0 and are included
        result = measure_session_length(sessions)
        session_lengths = result['session_lengths']
        assert len(session_lengths) == 3

        # With remove_zeros, only the session with explicit length is counted
        result = measure_session_length(sessions, remove_zeros=True)
        session_lengths = result['session_lengths']
        assert len(session_lengths) == 1
        assert session_lengths[0] == 5

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_return_types_are_floats(self, sample_sessions_basic):
        """Test that numeric return values are floats."""
        result = measure_session_length(sample_sessions_basic)

        float_keys = ['mean', 'var', 'std', 'min', 'max', 'range',
                     'median', 'q1', 'q3', 'middle_range']

        for key in float_keys:
            assert isinstance(result[key], float)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_five_most_common_correct_counts(self):
        """Test that most common counts are accurate."""
        sessions = [
            {"length": 5, "full_session": []},
            {"length": 5, "full_session": []},
            {"length": 5, "full_session": []},
            {"length": 3, "full_session": []},
            {"length": 3, "full_session": []},
            {"length": 7, "full_session": []}
        ]

        result = measure_session_length(sessions)

        five_most_common = result['five_most_common']

        # Should be: (5, 3), (3, 2), (7, 1)
        assert five_most_common[0] == (5, 3)  # 5 appears 3 times
        assert five_most_common[1] == (3, 2)  # 3 appears 2 times
        assert five_most_common[2] == (7, 1)  # 7 appears 1 time

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_session_lengths_array_type(self, sample_sessions_basic):
        """Test that session_lengths is a numpy array."""
        result = measure_session_length(sample_sessions_basic)

        assert isinstance(result['session_lengths'], np.ndarray)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_very_large_lengths(self):
        """Test with very large session lengths."""
        sessions = [
            {"length": 1000000, "full_session": []},
            {"length": 2000000, "full_session": []},
            {"length": 3000000, "full_session": []}
        ]

        result = measure_session_length(sessions)

        assert result['min'] == 1000000.0
        assert result['max'] == 3000000.0
        assert result['mean'] == 2000000.0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mixed_session_structure(self, sample_sessions_varied_tactics):
        """Test with sessions that have varied structures."""
        result = measure_session_length(sample_sessions_varied_tactics)

        # Lengths are [3, 4, 2]
        expected_mean = (3 + 4 + 2) / 3
        assert abs(result['mean'] - expected_mean) < 0.01

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_only_zero_length_sessions(self):
        """Test with sessions that all have zero length."""
        sessions = [
            {"length": 0, "full_session": []},
            {"length": 0, "full_session": []},
            {"length": 0, "full_session": []}
        ]

        # Without remove_zeros, zeros are included
        result = measure_session_length(sessions)
        assert len(result['session_lengths']) == 3
        assert result['mean'] == 0.0

        # With remove_zeros, empty array returns safe defaults
        result = measure_session_length(sessions, remove_zeros=True)
        assert len(result['session_lengths']) == 0
        assert result['mean'] == 0.0
        assert result['five_most_common'] == []
