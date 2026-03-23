# ABOUTME: Host-side LLM response cache utility for demo mode.
# ABOUTME: Provides normalize/load/save helpers for the Cowrie-side cache file.

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def normalize_cache_key(command: str) -> str:
    """Normalize a command for cache lookup: strip, collapse whitespace, lowercase."""
    return re.sub(r"\s+", " ", command.strip().lower())


def compute_profile_hash(profile: dict) -> str:
    """SHA-256 hash (truncated) of a profile dict for cache invalidation."""
    raw = json.dumps(profile, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_cache(path: Path | str) -> dict[str, Any]:
    """Load a cache file from disk. Returns empty structure on failure."""
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if "profile_hash" in data and "entries" in data:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"profile_hash": "", "entries": {}}


def save_cache(path: Path | str, data: dict[str, Any]) -> None:
    """Write cache data to disk as JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
