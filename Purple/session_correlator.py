"""Post-hoc session correlation across HoneyNet hops.

Reads each hop's Cowrie JSON log, correlates sessions by source IP
(pot1's IP on pot2 = same attacker), and builds per-journey metrics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from Blue_Lagoon.credential_chain import ChainManifest
from Blue_Lagoon.honeypot_tools import get_cowrie_log_path


@dataclass
class HopSession:
    """A single session on one hop."""
    hop_index: int
    session_id: str
    src_ip: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    commands: list[str] = field(default_factory=list)
    files_accessed: list[str] = field(default_factory=list)

    @property
    def dwell_time_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0


@dataclass
class AttackerJourney:
    """A correlated multi-hop journey by one attacker."""
    hop_sessions: list[HopSession] = field(default_factory=list)

    @property
    def total_dwell_time(self) -> float:
        if not self.hop_sessions:
            return 0.0
        starts = [s.start_time for s in self.hop_sessions if s.start_time]
        ends = [s.end_time for s in self.hop_sessions if s.end_time]
        if starts and ends:
            return (max(ends) - min(starts)).total_seconds()
        return sum(s.dwell_time_seconds for s in self.hop_sessions)

    @property
    def max_hop_reached(self) -> int:
        """Highest hop where the attacker actually executed commands."""
        if not self.hop_sessions:
            return 0
        active = [s for s in self.hop_sessions if s.commands]
        if not active:
            return 1  # At least hop 1 existed (session was created)
        return max(s.hop_index for s in active) + 1

    @property
    def pivot_success(self) -> bool:
        """True only if attacker executed commands on more than one hop."""
        active_hops = sum(1 for s in self.hop_sessions if s.commands)
        return active_hops > 1

    def summary(self) -> dict[str, Any]:
        return {
            "total_dwell_time_s": round(self.total_dwell_time, 2),
            "max_hop_reached": self.max_hop_reached,
            "pivot_success": self.pivot_success,
            "hops": [
                {
                    "hop": s.hop_index + 1,
                    "session_id": s.session_id,
                    "src_ip": s.src_ip,
                    "dwell_time_s": round(s.dwell_time_seconds, 2),
                    "num_commands": len(s.commands),
                    "files_accessed": s.files_accessed,
                }
                for s in self.hop_sessions
            ],
        }


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse Cowrie's timestamp format."""
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


def _read_hop_events(hop_index: int) -> list[dict]:
    """Read all events from a hop's Cowrie JSON log."""
    log_path = get_cowrie_log_path(hop_index)
    if not log_path.exists():
        return []

    events = []
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def _build_hop_sessions(hop_index: int) -> dict[str, HopSession]:
    """Parse events into sessions keyed by Cowrie session ID."""
    events = _read_hop_events(hop_index)
    sessions: dict[str, HopSession] = {}

    for event in events:
        event_id = event.get("eventid", "")
        session_id = event.get("session", "")
        ts = _parse_timestamp(event.get("timestamp", ""))

        if not session_id:
            continue

        if session_id not in sessions:
            sessions[session_id] = HopSession(
                hop_index=hop_index,
                session_id=session_id,
                src_ip=event.get("src_ip", ""),
            )

        sess = sessions[session_id]

        if event_id == "cowrie.session.connect":
            sess.start_time = ts
            sess.src_ip = event.get("src_ip", sess.src_ip)

        elif event_id == "cowrie.session.closed":
            sess.end_time = ts

        elif event_id == "cowrie.command.input":
            cmd = event.get("input", "")
            sess.commands.append(cmd)
            # Track file access commands (cat, less, head, tail, etc.)
            for prefix in ("cat ", "less ", "head ", "tail ", "more ", "vim ", "nano "):
                if cmd.startswith(prefix):
                    sess.files_accessed.append(cmd[len(prefix):].strip())

    return sessions


def correlate_sessions(manifest: ChainManifest) -> list[AttackerJourney]:
    """Build attacker journeys by correlating SSH sessions across hops.

    Algorithm:
    - Parse all events from each hop's log
    - For hop N+1, match sessions whose src_ip equals hop N's container IP
    - Chain: Kali->pot1(session) + pot1_ip->pot2(session) = one journey
    """
    num_hops = len(manifest.hops)

    # Build sessions per hop
    all_sessions: list[dict[str, HopSession]] = []
    for i in range(num_hops):
        all_sessions.append(_build_hop_sessions(i))

    if not all_sessions or not all_sessions[0]:
        return []

    # Build pot IP lookup: hop_index -> set of IPs that this pot uses
    # as source when connecting to other hops.
    # Star topology: all pots share net_attack, so pot N's src_ip when
    # connecting to pot M is pot N's attack_ip.
    # We also include the Kali IP since it can reach any hop directly.
    pot_ips: dict[int, set[str]] = {}
    kali_ip = f"172.{manifest.run_id}.0.2"
    for hop in manifest.hops:
        i = hop.hop_index
        # This pot's attack_ip is what other hops see as src_ip
        pot_ips.setdefault(i, set()).add(hop.attack_ip)
        # Also add internal_ip in case connections come via the internal net
        pot_ips[i].add(hop.internal_ip)

    # Start with hop0 sessions (these are attacker entries from Kali)
    journeys: list[AttackerJourney] = []

    # Track which sessions have already been claimed by a journey
    used_sessions: set[tuple[int, str]] = set()  # (hop_index, session_id)

    # All IPs that could be the attacker (Kali or any pot the attacker controls)
    attacker_ips: set[str] = {kali_ip}

    for sess_id, hop0_sess in all_sessions[0].items():
        journey = AttackerJourney(hop_sessions=[hop0_sess])
        used_sessions.add((0, sess_id))
        # After gaining hop0, the attacker can also SSH from hop0's IP
        attacker_ips.update(pot_ips.get(0, set()))

        # Try to find sessions on subsequent hops from any attacker-controlled IP
        for hop_idx in range(1, num_hops):
            hop_sessions = all_sessions[hop_idx]
            # Find sessions whose src_ip is any attacker-controlled IP
            matched = None
            best_cmd_count = -1
            for s_id, s in hop_sessions.items():
                if s.src_ip in attacker_ips and (hop_idx, s_id) not in used_sessions:
                    cmd_count = len(s.commands)
                    if cmd_count > best_cmd_count:
                        matched = s
                        best_cmd_count = cmd_count

            if matched:
                journey.hop_sessions.append(matched)
                used_sessions.add((hop_idx, matched.session_id))
                # Attacker now also controls this hop's IPs
                attacker_ips.update(pot_ips.get(hop_idx, set()))

        journeys.append(journey)

    return journeys


def print_correlation_report(journeys: list[AttackerJourney]) -> None:
    """Print a human-readable correlation report."""
    print(f"\n{'=' * 60}")
    print(f"HoneyNet Session Correlation Report")
    print(f"{'=' * 60}")
    print(f"Total journeys: {len(journeys)}")

    pivoted = sum(1 for j in journeys if j.pivot_success)
    print(f"Pivot success rate: {pivoted}/{len(journeys)} "
          f"({100 * pivoted / max(len(journeys), 1):.0f}%)")

    for i, journey in enumerate(journeys):
        print(f"\n--- Journey {i + 1} ---")
        print(f"  Total dwell time: {journey.total_dwell_time:.1f}s")
        print(f"  Max hop reached: {journey.max_hop_reached}")
        for hop_sess in journey.hop_sessions:
            print(f"  Hop {hop_sess.hop_index + 1}: "
                  f"{len(hop_sess.commands)} commands, "
                  f"{hop_sess.dwell_time_seconds:.1f}s dwell, "
                  f"from {hop_sess.src_ip}")
            if hop_sess.files_accessed:
                print(f"    Files accessed: {', '.join(hop_sess.files_accessed[:5])}")

    print(f"\n{'=' * 60}\n")
