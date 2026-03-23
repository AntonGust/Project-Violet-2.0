"""
Unit tests for Reconfigurator.new_config_pipeline (profile-based generation).
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from Reconfigurator.new_config_pipeline import (
    build_profile_prompt,
    finalize_profile,
    generate_new_profile,
    sample_previous_profiles,
    validate_profile,
)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "Reconfigurator" / "profiles"
SCHEMA_PATH = Path(__file__).resolve().parent.parent / "Reconfigurator" / "RagData" / "filesystem_profile_schema.json"


@pytest.fixture
def sample_profile():
    """Load wordpress_server.json as a sample profile."""
    with open(PROFILES_DIR / "wordpress_server.json") as f:
        return json.load(f)


@pytest.fixture
def minimal_profile():
    """A minimal valid profile structure."""
    return {
        "system": {
            "os": "Debian 11",
            "hostname": "test-srv",
            "kernel_version": "5.10.0-20-amd64",
            "arch": "x86_64",
        },
        "users": [
            {"name": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash"}
        ],
        "directory_tree": {
            "/": [{"name": "root", "type": "dir"}]
        },
        "file_contents": {
            "/etc/hostname": "test-srv"
        },
        "services": [
            {"name": "sshd", "pid": 1, "user": "root", "command": "/usr/sbin/sshd -D", "ports": [22]}
        ],
        "ssh_config": {
            "accepted_passwords": {"root": ["root", "123456"]}
        },
        "description": "Test server",
    }


# ---------------------------------------------------------------------------
# finalize_profile
# ---------------------------------------------------------------------------


class TestFinalizeProfile:
    def test_assigns_uuid_and_timestamp(self, minimal_profile):
        result = finalize_profile(minimal_profile)
        assert "id" in result
        assert len(result["id"]) == 36  # UUID format
        assert "timestamp" in result

    def test_root_user_enforced(self):
        profile = {
            "users": [
                {"name": "deploy", "uid": 1000, "gid": 1000, "home": "/home/deploy", "shell": "/bin/bash"}
            ],
            "ssh_config": {},
        }
        result = finalize_profile(profile)
        user_names = [u["name"] for u in result["users"]]
        assert "root" in user_names
        assert user_names[0] == "root"

    def test_root_passwords_enforced(self):
        profile = {"users": [{"name": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash"}], "ssh_config": {}}
        result = finalize_profile(profile)
        assert "root" in result["ssh_config"]["accepted_passwords"]
        assert "root" in result["ssh_config"]["accepted_passwords"]["root"]

    def test_existing_root_passwords_preserved(self):
        profile = {
            "users": [{"name": "root", "uid": 0, "gid": 0, "home": "/root", "shell": "/bin/bash"}],
            "ssh_config": {"accepted_passwords": {"root": ["toor", "password"]}},
        }
        result = finalize_profile(profile)
        assert result["ssh_config"]["accepted_passwords"]["root"] == ["toor", "password"]


# ---------------------------------------------------------------------------
# build_profile_prompt
# ---------------------------------------------------------------------------


class TestBuildProfilePrompt:
    def test_includes_schema(self):
        schema = '{"type": "object", "properties": {}}'
        prompt = build_profile_prompt(schema, [])
        assert "## JSON Schema" in prompt
        assert '"type": "object"' in prompt

    def test_includes_previous_profiles(self, sample_profile):
        schema = "{}"
        prev = [{"profile": sample_profile, "sessions": None}]
        prompt = build_profile_prompt(schema, prev)
        assert "Previous Profiles" in prompt
        assert sample_profile["system"]["hostname"] in prompt

    def test_includes_session_tactics(self, sample_profile):
        schema = "{}"
        prev = [{"profile": sample_profile, "sessions": [{"tactics": ["Discovery", "Execution"], "techniques": ["T1059"]}]}]
        prompt = build_profile_prompt(schema, prev)
        assert "Discovery" in prompt
        assert "T1059" in prompt

    def test_empty_previous_profiles(self):
        schema = "{}"
        prompt = build_profile_prompt(schema, [])
        assert "Previous Profiles" not in prompt


# ---------------------------------------------------------------------------
# sample_previous_profiles
# ---------------------------------------------------------------------------


class TestSamplePreviousProfiles:
    def test_loads_profiles_from_experiment_dir(self, sample_profile):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "hp_config_1"
            config_dir.mkdir()
            with open(config_dir / "honeypot_config.json", "w") as f:
                json.dump(sample_profile, f)
            with open(config_dir / "sessions.json", "w") as f:
                json.dump([{"tactics": ["Discovery"]}], f)

            results = sample_previous_profiles(tmpdir)
            assert len(results) == 1
            assert results[0]["profile"]["system"]["hostname"] == sample_profile["system"]["hostname"]
            assert results[0]["sessions"] is not None

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = sample_previous_profiles(tmpdir)
            assert results == []

    def test_missing_sessions_file(self, sample_profile):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "hp_config_1"
            config_dir.mkdir()
            with open(config_dir / "honeypot_config.json", "w") as f:
                json.dump(sample_profile, f)

            results = sample_previous_profiles(tmpdir)
            assert len(results) == 1
            assert results[0]["sessions"] is None


# ---------------------------------------------------------------------------
# validate_profile
# ---------------------------------------------------------------------------


class TestValidateProfile:
    def test_valid_profile(self, sample_profile):
        assert validate_profile(sample_profile) is True

    def test_missing_required_field(self):
        invalid = {"system": {"os": "Ubuntu"}}
        assert validate_profile(invalid) is False


# ---------------------------------------------------------------------------
# generate_new_profile (integration with mocked OpenAI)
# ---------------------------------------------------------------------------


class TestGenerateNewProfile:
    def test_integration_with_mocked_openai(self, minimal_profile):
        """Mock OpenAI to return a valid profile, verify full pipeline."""
        # Remove id/timestamp — finalize_profile will add them
        minimal_profile.pop("id", None)
        minimal_profile.pop("timestamp", None)
        llm_response = json.dumps(minimal_profile)

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "Reconfigurator.new_config_pipeline.query_openai",
                return_value=llm_response,
            ):
                result = generate_new_profile(tmpdir)

        assert result is not None
        assert "id" in result
        assert "timestamp" in result
        assert validate_profile(result) is True

    def test_returns_none_after_failures(self):
        """If OpenAI always returns garbage, we get None after 3 retries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch(
                "Reconfigurator.new_config_pipeline.query_openai",
                return_value="not valid json at all",
            ):
                result = generate_new_profile(tmpdir)

        assert result is None
