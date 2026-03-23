"""
Tests for metrics/sequences.py functions.

Tests sequence extraction and indexing for tactics, techniques, and commands.
"""

import pytest
import numpy as np
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from Purple.metrics.sequences import (
    measure_tactic_sequences,
    measure_technique_sequences,
    measure_command_sequences,
    measure_sequences
)


class TestMeasureSequences:
    """Tests for measure_sequences function (base function)."""

    @pytest.mark.unit
    def test_sequences_tactic_structure(self, sample_sessions_varied_tactics):
        """Test sequence extraction for tactics."""
        result = measure_sequences(sample_sessions_varied_tactics, "tactic")

        # Check expected keys
        assert 'tactic' in result
        assert 'sequences' in result
        assert 'indexed_sequences' in result

    @pytest.mark.unit
    def test_sequences_technique_structure(self, sample_sessions_varied_tactics):
        """Test sequence extraction for techniques."""
        result = measure_sequences(sample_sessions_varied_tactics, "technique")

        assert 'technique' in result
        assert 'sequences' in result
        assert 'indexed_sequences' in result

    @pytest.mark.unit
    def test_sequences_command_structure(self, sample_sessions_varied_tactics):
        """Test sequence extraction for commands."""
        result = measure_sequences(sample_sessions_varied_tactics, "command")

        assert 'command' in result
        assert 'sequences' in result
        assert 'indexed_sequences' in result

    @pytest.mark.unit
    def test_sequences_mapping_created(self, sample_sessions_basic):
        """Test that mapping dictionary is created."""
        result = measure_sequences(sample_sessions_basic, "tactic")

        tactic_map = result['tactic']

        # Should be a dict mapping tactics to indices
        assert isinstance(tactic_map, dict)
        assert 'Discovery' in tactic_map
        assert isinstance(tactic_map['Discovery'], int)

    @pytest.mark.unit
    def test_sequences_list_length(self, sample_sessions_basic):
        """Test that sequences list matches number of sessions."""
        result = measure_sequences(sample_sessions_basic, "tactic")

        sequences = result['sequences']
        indexed_sequences = result['indexed_sequences']

        num_sessions = len(sample_sessions_basic)

        assert len(sequences) == num_sessions
        assert len(indexed_sequences) == num_sessions

    @pytest.mark.unit
    def test_sequences_indexed_correctly(self, sample_sessions_basic):
        """Test that indexed sequences use correct mapping."""
        result = measure_sequences(sample_sessions_basic, "tactic")

        tactic_map = result['tactic']
        sequences = result['sequences']
        indexed_sequences = result['indexed_sequences']

        # Check first session
        for i, tactic in enumerate(sequences[0]):
            expected_index = tactic_map[tactic]
            actual_index = indexed_sequences[0][i]
            assert actual_index == expected_index

    @pytest.mark.unit
    def test_sequences_command_splits_on_space(self):
        """Test that command sequences only use first word."""
        sessions = [
            {
                "length": 2,
                "full_session": [
                    {"command": "ls -la", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "cat /etc/passwd", "tactic": "Discovery", "technique": "T1087"}
                ]
            }
        ]

        result = measure_sequences(sessions, "command")

        sequences = result['sequences']

        # Should only have "ls" and "cat", not full commands
        assert "ls" in sequences[0]
        assert "cat" in sequences[0]
        assert "ls -la" not in sequences[0]

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_sequences_empty_session(self):
        """Test handling of empty sessions."""
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

        result = measure_sequences(sessions, "tactic")

        sequences = result['sequences']

        # First session should be empty
        assert len(sequences[0]) == 0

        # Second session should have data
        assert len(sequences[1]) == 2

    @pytest.mark.unit
    def test_sequences_unique_items_indexed(self, sample_sessions_varied_tactics):
        """Test that all unique items are indexed."""
        result = measure_sequences(sample_sessions_varied_tactics, "tactic")

        tactic_map = result['tactic']

        # All indices should be unique
        indices = list(tactic_map.values())
        assert len(indices) == len(set(indices))

        # Indices should start at 0 and be consecutive
        assert min(indices) == 0
        assert max(indices) == len(indices) - 1

    @pytest.mark.unit
    def test_sequences_preserves_order(self, sample_sessions_basic):
        """Test that sequence order is preserved."""
        result = measure_sequences(sample_sessions_basic, "technique")

        sequences = result['sequences']

        # First session should have techniques in order
        # Check that it matches the original session order
        first_session = sample_sessions_basic[0]
        expected_techniques = [cmd['technique'] for cmd in first_session['full_session']]

        assert sequences[0] == expected_techniques

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_sequences_missing_field(self):
        """Test handling of missing tactic/technique/command fields."""
        sessions = [
            {
                "length": 2,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {}  # Empty command entry
                ]
            }
        ]

        result = measure_sequences(sessions, "tactic")

        sequences = result['sequences']

        # Should have empty string for missing field
        assert len(sequences[0]) == 2
        assert sequences[0][1] == ""

    @pytest.mark.unit
    def test_sequences_repeated_items(self):
        """Test that repeated items get same index."""
        sessions = [
            {
                "length": 3,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "pwd", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"}
                ]
            }
        ]

        result = measure_sequences(sessions, "command")

        command_map = result['command']
        indexed_sequences = result['indexed_sequences']

        # "ls" should have same index in positions 0 and 2
        assert indexed_sequences[0][0] == indexed_sequences[0][2]
        assert indexed_sequences[0][0] == command_map['ls']


class TestMeasureTacticSequences:
    """Tests for measure_tactic_sequences wrapper function."""

    @pytest.mark.unit
    def test_tactic_sequences_wrapper(self, sample_sessions_varied_tactics):
        """Test that tactic sequences wrapper works correctly."""
        result = measure_tactic_sequences(sample_sessions_varied_tactics)

        assert 'tactic' in result
        assert 'sequences' in result

        # Should have tactics like "Discovery", not technique IDs
        tactic_map = result['tactic']
        assert any('Discovery' in key or 'Execution' in key
                  for key in tactic_map.keys())

    @pytest.mark.unit
    def test_tactic_sequences_basic(self, sample_sessions_basic):
        """Test tactic sequence extraction with basic sessions."""
        result = measure_tactic_sequences(sample_sessions_basic)

        sequences = result['sequences']

        # All commands in first session are Discovery
        assert all(tactic == 'Discovery' for tactic in sequences[0])


class TestMeasureTechniqueSequences:
    """Tests for measure_technique_sequences wrapper function."""

    @pytest.mark.unit
    def test_technique_sequences_wrapper(self, sample_sessions_varied_tactics):
        """Test that technique sequences wrapper works correctly."""
        result = measure_technique_sequences(sample_sessions_varied_tactics)

        assert 'technique' in result
        assert 'sequences' in result

        # Should have technique IDs like "T1083"
        technique_map = result['technique']
        assert any(key.startswith('T') for key in technique_map.keys())

    @pytest.mark.unit
    def test_technique_sequences_basic(self, sample_sessions_basic):
        """Test technique sequence extraction with basic sessions."""
        result = measure_technique_sequences(sample_sessions_basic)

        sequences = result['sequences']
        technique_map = result['technique']

        # Should have techniques from the session
        assert 'T1083' in technique_map
        assert 'T1033' in technique_map


class TestMeasureCommandSequences:
    """Tests for measure_command_sequences wrapper function."""

    @pytest.mark.unit
    def test_command_sequences_wrapper(self, sample_sessions_varied_tactics):
        """Test that command sequences wrapper works correctly."""
        result = measure_command_sequences(sample_sessions_varied_tactics)

        assert 'command' in result
        assert 'sequences' in result

        # Should have command names
        command_map = result['command']
        assert 'ls' in command_map or 'pwd' in command_map or 'whoami' in command_map

    @pytest.mark.unit
    def test_command_sequences_basic(self, sample_sessions_basic):
        """Test command sequence extraction with basic sessions."""
        result = measure_command_sequences(sample_sessions_basic)

        sequences = result['sequences']
        command_map = result['command']

        # Should extract first word of commands
        assert 'ls' in command_map
        assert 'whoami' in command_map
        assert 'cat' in command_map

        # First sequence should start with "ls"
        assert sequences[0][0] == 'ls'

    @pytest.mark.unit
    def test_command_sequences_splits_arguments(self):
        """Test that command arguments are removed."""
        sessions = [
            {
                "length": 3,
                "full_session": [
                    {"command": "ls -la /home", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "cat /etc/passwd", "tactic": "Discovery", "technique": "T1087"},
                    {"command": "grep root /etc/passwd", "tactic": "Discovery", "technique": "T1087"}
                ]
            }
        ]

        result = measure_command_sequences(sessions)

        command_map = result['command']
        sequences = result['sequences']

        # Should only have base commands
        assert 'ls' in command_map
        assert 'cat' in command_map
        assert 'grep' in command_map

        # Sequences should have base commands only
        assert sequences[0] == ['ls', 'cat', 'grep']


class TestSequencesIntegration:
    """Integration tests for all sequence functions."""

    @pytest.mark.unit
    def test_all_sequence_types_on_same_data(self, sample_sessions_varied_tactics):
        """Test all three sequence types on the same data."""
        tactic_result = measure_tactic_sequences(sample_sessions_varied_tactics)
        technique_result = measure_technique_sequences(sample_sessions_varied_tactics)
        command_result = measure_command_sequences(sample_sessions_varied_tactics)

        # All should have same number of sessions
        assert len(tactic_result['sequences']) == len(sample_sessions_varied_tactics)
        assert len(technique_result['sequences']) == len(sample_sessions_varied_tactics)
        assert len(command_result['sequences']) == len(sample_sessions_varied_tactics)

        # All should have same sequence lengths per session
        for i in range(len(sample_sessions_varied_tactics)):
            assert len(tactic_result['sequences'][i]) == len(technique_result['sequences'][i])
            assert len(technique_result['sequences'][i]) == len(command_result['sequences'][i])

    @pytest.mark.unit
    def test_indexed_sequences_match_original(self, sample_sessions_basic):
        """Test that indexed sequences can be reverse-mapped to originals."""
        result = measure_tactic_sequences(sample_sessions_basic)

        tactic_map = result['tactic']
        sequences = result['sequences']
        indexed_sequences = result['indexed_sequences']

        # Create reverse mapping
        reverse_map = {v: k for k, v in tactic_map.items()}

        # Verify we can reconstruct original sequences
        for i in range(len(sequences)):
            reconstructed = [reverse_map[idx] for idx in indexed_sequences[i]]
            assert reconstructed == sequences[i]

    @pytest.mark.unit
    @pytest.mark.edge_case
    def test_single_command_session(self):
        """Test with session containing single command."""
        sessions = [
            {
                "length": 1,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"}
                ]
            }
        ]

        result = measure_command_sequences(sessions)

        assert len(result['sequences'][0]) == 1
        assert result['sequences'][0][0] == 'ls'

    @pytest.mark.unit
    def test_sequences_with_varying_lengths(self):
        """Test sequences with sessions of varying lengths."""
        sessions = [
            {
                "length": 1,
                "full_session": [
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"}
                ]
            },
            {
                "length": 5,
                "full_session": [
                    {"command": "pwd", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "ls", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "cat", "tactic": "Discovery", "technique": "T1083"},
                    {"command": "whoami", "tactic": "Discovery", "technique": "T1033"},
                    {"command": "id", "tactic": "Discovery", "technique": "T1033"}
                ]
            }
        ]

        result = measure_command_sequences(sessions)

        sequences = result['sequences']

        assert len(sequences[0]) == 1
        assert len(sequences[1]) == 5

    @pytest.mark.unit
    def test_empty_string_handling(self):
        """Test handling of empty strings in fields."""
        sessions = [
            {
                "length": 2,
                "full_session": [
                    {"command": "ls", "tactic": "", "technique": ""},
                    {"command": "pwd", "tactic": "Discovery", "technique": "T1083"}
                ]
            }
        ]

        result = measure_tactic_sequences(sessions)

        sequences = result['sequences']

        # Empty strings should be preserved
        assert sequences[0][0] == ""
        assert sequences[0][1] == "Discovery"
