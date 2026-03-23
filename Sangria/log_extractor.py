import json

from pathlib import Path

import config as cfg

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COWRIE_JSON_LOG = PROJECT_ROOT / "cowrie_config" / "var" / "log" / "cowrie" / "cowrie.json"

_file_offset = 0


def _get_log_path() -> Path:
    """Return the log path for the primary pot (pot1 in honeynet mode)."""
    if cfg.honeynet_enabled:
        return PROJECT_ROOT / "cowrie_config_hop1" / "var" / "log" / "cowrie" / "cowrie.json"
    return COWRIE_JSON_LOG


def reset_offset():
    """Reset the file offset so old events are not re-read.

    Must be called whenever ``clear_hp_logs()`` runs (or whenever Docker
    containers are restarted) so that this module's offset stays in sync
    with the actual log file state.
    """
    global _file_offset
    log_path = _get_log_path()
    if log_path.exists():
        _file_offset = log_path.stat().st_size
    else:
        _file_offset = 0


def get_new_hp_logs():
    """
    Read new Cowrie JSON events from the host-mounted log file.
    Tracks byte offset between calls so only new lines are returned.

    In honeynet mode, reads pot1's log (the entry pot where Sangria
    connects). Commands relayed to inner pots via the SSH proxy are
    logged by those pots, not pot1.

    Returns a list of event dicts in the format expected by extraction.py:
    [{"level": "info", "status": "Interaction", "event": {...}}, ...]
    """
    global _file_offset

    log_path = _get_log_path()

    if not log_path.exists():
        return []

    file_size = log_path.stat().st_size
    if file_size < _file_offset:
        _file_offset = 0

    if file_size == _file_offset:
        return []

    events = []

    with open(log_path, "r") as f:
        f.seek(_file_offset)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_id = event.get("eventid", "")

            if event_id != "cowrie.command.input":
                continue

            cmd = event.get("input", "")
            events.append({
                "level": "info",
                "status": "Interaction",
                "event": {
                    "Protocol": "SSH",
                    "Command": cmd,
                    "CommandOutput": "",
                    "User": event.get("username", "root"),
                    "Timestamp": event.get("timestamp", ""),
                },
            })

        _file_offset = f.tell()

    return events
