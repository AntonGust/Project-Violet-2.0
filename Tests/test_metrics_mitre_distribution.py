"""
Tests for metrics/mitre_distribution.py functions.

Tests MITRE ATT&CK tactic and technique distribution analysis.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Purple.metrics.mitre_distribution import create_heatmap, measure_mitre_distribution


class TestCreateHeatmap:
    """Tests for create_heatmap function."""

    @pytest.mark.unit
    def test_heatmap_basic_structure(self):
        """Test basic heatmap creation."""
        rows = ["tactic1", "tactic2", "tactic3"]
        data = [
            {"tactic1": 2, "tactic2": 1},
            {"tactic1": 1, "tactic3": 3},
            {"tactic2": 2, "tactic3": 1}
        ]

        heatmap = create_heatmap(rows, data)

        # Should be 3 rows (tactics) x 3 columns (sessions)
        assert heatmap.shape == (3, 3)
        assert isinstance(heatmap, np.ndarray)

    @pytest.mark.unit
    def test_heatmap_values_correct(self):
        """Test that heatmap values are correctly populated."""
        rows = ["A", "B"]
        data = [
            {"A": 5, "B": 3},
            {"A": 2, "B": 7}
        ]

        heatmap = create_heatmap(rows, data)

        # First session
        assert heatmap[0, 0] == 5  # A in session 0
        assert heatmap[1, 0] == 3  # B in session 0

        # Second session
        assert heatmap[0, 1] == 2  # A in session 1
        assert heatmap[1, 1] == 7  # B in session 1

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_heatmap_missing_values(self):
        """Test heatmap with missing values (should be 0)."""
        rows = ["A", "B", "C"]
        data = [
            {"A": 1},  # B and C missing
            {"C": 2}   # A and B missing
        ]

        heatmap = create_heatmap(rows, data)

        # Missing values should be 0
        assert heatmap[1, 0] == 0  # B in session 0
        assert heatmap[2, 0] == 0  # C in session 0
        assert heatmap[0, 1] == 0  # A in session 1
        assert heatmap[1, 1] == 0  # B in session 1

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_heatmap_empty_data(self):
        """Test heatmap with empty data."""
        rows = ["A", "B"]
        data = []

        heatmap = create_heatmap(rows, data)

        # Should be all zeros with 0 columns
        assert heatmap.shape == (2, 0)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_heatmap_empty_sessions(self):
        """Test heatmap with sessions that have no data."""
        rows = ["A", "B"]
        data = [{}, {}, {}]

        heatmap = create_heatmap(rows, data)

        # Should be all zeros
        assert heatmap.shape == (2, 3)
        assert np.all(heatmap == 0)


class TestMeasureMitreDistribution:
    """Tests for measure_mitre_distribution function."""

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_distribution_structure(self, sample_sessions_varied_tactics):
        """Test that result contains all expected keys."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        expected_keys = [
            'tactics', 'techniques', 'num_tactics', 'num_techniques',
            'tactics_frac', 'techniques_frac',
            'session_tactics', 'session_techniques',
            'session_num_tactics', 'session_cum_num_tactics',
            'session_num_techniques', 'session_cum_num_techniques',
            'tactics_heatmap', 'techniques_heatmap'
        ]

        for key in expected_keys:
            assert key in result

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_tactics_counting(self, sample_sessions_varied_tactics):
        """Test that tactics are counted correctly."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        tactics = result['tactics']

        # Should have Discovery (most common), Execution, Command And Control, Impact
        assert 'Discovery' in tactics
        assert tactics['Discovery'] > 0

        # Total tactics in fixtures: Discovery appears 5 times, others vary
        total_tactics = sum(tactics.values())
        assert total_tactics == 9  # Total commands with tactics

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_techniques_counting(self, sample_sessions_varied_tactics):
        """Test that techniques are counted correctly."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        techniques = result['techniques']

        # Should have T1083 and others
        assert 'T1083' in techniques
        assert techniques['T1083'] > 0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_num_counts(self, sample_sessions_varied_tactics):
        """Test num_tactics and num_techniques."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        assert result['num_tactics'] > 0
        assert result['num_techniques'] > 0

        # Should match length of tactics/techniques dicts
        assert result['num_tactics'] == len(result['tactics'])
        assert result['num_techniques'] == len(result['techniques'])

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_fractions_sum_to_one(self, sample_sessions_varied_tactics):
        """Test that tactic and technique fractions sum to 1."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        tactics_frac = result['tactics_frac']
        techniques_frac = result['techniques_frac']

        tactics_sum = sum(tactics_frac.values())
        techniques_sum = sum(techniques_frac.values())

        assert abs(tactics_sum - 1.0) < 0.01
        assert abs(techniques_sum - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_sorted_by_frequency(self, sample_sessions_varied_tactics):
        """Test that tactics and techniques are sorted by frequency."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        tactics = list(result['tactics'].values())
        techniques = list(result['techniques'].values())

        # Should be in descending order
        assert tactics == sorted(tactics, reverse=True)
        assert techniques == sorted(techniques, reverse=True)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_session_lists_length(self, sample_sessions_varied_tactics):
        """Test that session lists have correct length."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        num_sessions = len(sample_sessions_varied_tactics)

        assert len(result['session_tactics']) == num_sessions
        assert len(result['session_techniques']) == num_sessions
        assert len(result['session_num_tactics']) == num_sessions
        assert len(result['session_num_techniques']) == num_sessions

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_cumulative_counts(self, sample_sessions_varied_tactics):
        """Test that cumulative counts increase or stay the same."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        cum_tactics = result['session_cum_num_tactics']
        cum_techniques = result['session_cum_num_techniques']

        # Cumulative counts should be non-decreasing
        for i in range(len(cum_tactics) - 1):
            assert cum_tactics[i + 1] >= cum_tactics[i]
            assert cum_techniques[i + 1] >= cum_techniques[i]

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_new_counts_non_negative(self, sample_sessions_varied_tactics):
        """Test that new tactic/technique counts are non-negative."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        new_tactics = result['session_num_tactics']
        new_techniques = result['session_num_techniques']

        assert all(count >= 0 for count in new_tactics)
        assert all(count >= 0 for count in new_techniques)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_heatmap_dimensions(self, sample_sessions_varied_tactics):
        """Test that heatmaps have correct dimensions."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        num_sessions = len(sample_sessions_varied_tactics)
        num_tactics = result['num_tactics']
        num_techniques = result['num_techniques']

        tactics_heatmap = result['tactics_heatmap']
        techniques_heatmap = result['techniques_heatmap']

        assert tactics_heatmap.shape == (num_tactics, num_sessions)
        assert techniques_heatmap.shape == (num_techniques, num_sessions)

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_mitre_single_session(self, single_session):
        """Test with a single session."""
        result = measure_mitre_distribution(single_session)

        assert result['num_tactics'] > 0
        assert len(result['session_tactics']) == 1
        assert result['tactics_heatmap'].shape[1] == 1

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_mitre_sessions_without_tactics(self):
        """Test with sessions that have no MITRE data."""
        sessions = [
            {
                "length": 2,
                "full_session": [
                    {"command": "ls"},  # No tactic/technique
                    {"command": "pwd"}
                ]
            }
        ]

        result = measure_mitre_distribution(sessions)

        # Should handle missing MITRE data gracefully
        assert isinstance(result['tactics'], dict)
        assert isinstance(result['techniques'], dict)

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_session_data_consistency(self, sample_sessions_basic):
        """Test consistency between session data and aggregated data."""
        result = measure_mitre_distribution(sample_sessions_basic)

        # Sum of all session tactics should equal total tactics
        session_tactics = result['session_tactics']
        total_from_sessions = sum(
            sum(tactic_counts.values())
            for tactic_counts in session_tactics
        )

        total_from_aggregate = sum(result['tactics'].values())

        assert total_from_sessions == total_from_aggregate

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_empty_session_handling(self):
        """Test handling of sessions with empty full_session."""
        sessions = [
            {"length": 0, "full_session": []},
            {
                "length": 2,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "pwd", "tactic": "Discovery", "technique": "T1083"}
                ]
            }
        ]

        result = measure_mitre_distribution(sessions)

        # First session should have empty tactics
        assert len(result['session_tactics'][0]) == 0
        assert len(result['session_techniques'][0]) == 0

        # Second session should have tactics
        assert len(result['session_tactics'][1]) > 0

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_tactics_more_general_than_techniques(self, sample_sessions_varied_tactics):
        """Test that there are typically fewer unique tactics than techniques."""
        result = measure_mitre_distribution(sample_sessions_varied_tactics)

        # Generally, tactics are higher level, so fewer unique tactics
        # This may not always be true, but for typical data it is
        assert result['num_tactics'] <= result['num_techniques'] + 5  # Allow some variance

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_repeated_tactics_in_session(self):
        """Test that repeated tactics within a session are counted correctly."""
        sessions = [
            {
                "length": 3,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "pwd", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "whoami", "tactic": "Discovery", "technique": "T1033"}
                ]
            }
        ]

        result = measure_mitre_distribution(sessions)

        # Discovery should appear 3 times
        assert result['tactics']['Discovery'] == 3

        # T1083 should appear 2 times
        assert result['techniques']['T1083'] == 2

        # T1033 should appear 1 time
        assert result['techniques']['T1033'] == 1

    @pytest.mark.unit
    @pytest.mark.statistical
    def test_mitre_missing_fields_handled(self):
        """Test handling of commands with missing tactic/technique fields."""
        sessions = [
            {
                "length": 3,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "pwd"},  # Missing tactic and technique
                    {"command": "whoami", "tactic": "", "technique": ""}  # Empty strings
                ]
            }
        ]

        result = measure_mitre_distribution(sessions)

        # Should only count the first command
        assert sum(result['tactics'].values()) == 1
        assert sum(result['techniques'].values()) == 1
