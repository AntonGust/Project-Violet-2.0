"""Credential chain management for multi-hop HoneyNet deployments.

Builds a chain manifest mapping each hop's IP, credentials, and hostname,
then injects breadcrumbs pointing to the next hop into each profile.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class HopInfo:
    hop_index: int
    ip_from_prev: str       # IP as seen from previous hop's network
    ssh_port: int            # always 2222
    username: str            # SSH user for this hop
    password: str            # SSH password for this hop
    hostname: str            # from profile system.hostname
    profile_path: str


@dataclass
class ChainManifest:
    hops: list[HopInfo]
    run_id: str


def build_chain_manifest(run_id: str, chain_profiles: list[str]) -> ChainManifest:
    """Load each profile and build the chain manifest with IPs and credentials.

    IP scheme (matches compose_generator.py):
    - Pot1 on net_entry: 172.{run_id}.0.10
    - Pot2 on net_hop1:  172.{run_id}.1.11
    - Pot3 on net_hop2:  172.{run_id}.2.12
    - PotN on net_hop{N-1}: 172.{run_id}.{N-1}.{10+N-1}
    """
    hops: list[HopInfo] = []

    for i, profile_rel in enumerate(chain_profiles):
        profile_path = PROJECT_ROOT / profile_rel
        with open(profile_path) as f:
            profile = json.load(f)

        # Extract hostname
        hostname = profile.get("system", {}).get("hostname", f"hop{i + 1}")

        # Extract first accepted credential
        accepted = profile.get("ssh_config", {}).get("accepted_passwords", {})
        username = "root"
        password = "123456"
        for user, passwords in accepted.items():
            if passwords:
                username = user
                password = passwords[0]
                break

        # IP as seen from the previous hop's shared network
        if i == 0:
            ip_from_prev = f"172.{run_id}.0.10"
        else:
            ip_from_prev = f"172.{run_id}.{i}.{10 + i}"

        hops.append(HopInfo(
            hop_index=i,
            ip_from_prev=ip_from_prev,
            ssh_port=2222,
            username=username,
            password=password,
            hostname=hostname,
            profile_path=profile_rel,
        ))

    return ChainManifest(hops=hops, run_id=run_id)


def inject_next_hop_breadcrumbs(
    profile: dict,
    current_hop: HopInfo,
    next_hop: HopInfo,
) -> dict:
    """Inject real next-hop credentials into the profile dict.

    Modifies:
    1. /etc/hosts — adds hostname mapping for next hop
    2. .bash_history — adds SSH commands to next hop
    3. ~/.ssh/config — adds Host block for next hop
    4. lateral_movement_targets in lure files
    5. A .env breadcrumb with connection info

    Returns the modified profile (also mutates in-place).
    """
    next_ip = next_hop.ip_from_prev
    next_user = next_hop.username
    next_pass = next_hop.password
    next_host = next_hop.hostname
    next_port = next_hop.ssh_port

    # --- 1. /etc/hosts ---
    _inject_etc_hosts(profile, next_ip, next_host)

    # --- 2. .bash_history ---
    _inject_bash_history(profile, next_ip, next_user, next_pass, next_port)

    # --- 3. ~/.ssh/config ---
    _inject_ssh_config(profile, next_ip, next_user, next_host, next_port)

    # --- 4. Lure file breadcrumbs ---
    _inject_lure_breadcrumbs(profile, next_ip, next_user, next_pass, next_host, next_port)

    # --- 5. lateral_movement_targets ---
    _ensure_lateral_movement_target(profile, next_ip)

    return profile


def _inject_etc_hosts(profile: dict, ip: str, hostname: str) -> None:
    """Add a hosts entry in the profile's file_contents for /etc/hosts."""
    file_contents = profile.setdefault("file_contents", {})
    hosts_content = file_contents.get("/etc/hosts", "127.0.0.1\tlocalhost\n")
    if ip not in hosts_content:
        # Ensure trailing newline before appending
        if hosts_content and not hosts_content.endswith("\n"):
            hosts_content += "\n"
        hosts_content += f"{ip}\t{hostname}\n"
    file_contents["/etc/hosts"] = hosts_content


def _inject_bash_history(profile: dict, ip: str, user: str, password: str, port: int) -> None:
    """Add SSH commands to .bash_history in file_contents."""
    file_contents = profile.setdefault("file_contents", {})

    # Find the root user's home for history file path
    home = "/root"
    for u in profile.get("users", []):
        if u.get("name") == "root":
            home = u.get("home", "/root")
            break

    history_path = f"{home}/.bash_history"
    history = file_contents.get(history_path, "")

    # Ensure trailing newline before appending
    if history and not history.endswith("\n"):
        history += "\n"

    new_entries = [
        f"ssh {user}@{ip} -p {port}",
        f"sshpass -p '{password}' ssh {user}@{ip} -p {port}",
        f"ssh {user}@{ip}",
    ]
    for entry in new_entries:
        if entry not in history:
            history += entry + "\n"

    file_contents[history_path] = history


def _inject_ssh_config(profile: dict, ip: str, user: str, hostname: str, port: int) -> None:
    """Add an SSH config Host block in file_contents."""
    file_contents = profile.setdefault("file_contents", {})

    # Find root's home
    home = "/root"
    for u in profile.get("users", []):
        if u.get("name") == "root":
            home = u.get("home", "/root")
            break

    ssh_config_path = f"{home}/.ssh/config"
    ssh_config = file_contents.get(ssh_config_path, "")

    if ip not in ssh_config:
        block = (
            f"\nHost {hostname}\n"
            f"    HostName {ip}\n"
            f"    User {user}\n"
            f"    Port {port}\n"
            f"    StrictHostKeyChecking no\n"
        )
        ssh_config += block

    file_contents[ssh_config_path] = ssh_config


def _inject_lure_breadcrumbs(
    profile: dict, ip: str, user: str, password: str, hostname: str, port: int,
) -> None:
    """Add credential references to lure-style config files."""
    file_contents = profile.setdefault("file_contents", {})

    # Add a .env file with internal connection info
    env_path = "/opt/.env"
    env_content = file_contents.get(env_path, "")
    if ip not in env_content:
        env_content += (
            f"\n# Internal infrastructure\n"
            f"INTERNAL_HOST={ip}\n"
            f"INTERNAL_SSH_USER={user}\n"
            f"INTERNAL_SSH_PASS={password}\n"
            f"INTERNAL_SSH_PORT={port}\n"
            f"INTERNAL_HOSTNAME={hostname}\n"
        )
    file_contents[env_path] = env_content

    # Ensure /opt/.env appears in directory_tree
    dir_tree = profile.setdefault("directory_tree", {})
    opt_entries = dir_tree.setdefault("/opt", [])
    if not any(e.get("name") == ".env" for e in opt_entries):
        opt_entries.append({
            "name": ".env",
            "type": "file",
            "permissions": "0644",
            "owner": "root",
            "group": "root",
            "size": len(env_content),
        })


def _ensure_lateral_movement_target(profile: dict, ip: str) -> None:
    """Ensure the next hop IP is in the profile's lateral_movement_targets."""
    lures = profile.setdefault("lures", {})
    lat_targets = lures.setdefault("lateral_movement_targets", [])

    # Check if IP is already present
    for target in lat_targets:
        if isinstance(target, dict) and target.get("ip") == ip:
            return
        if isinstance(target, str) and ip in target:
            return

    lat_targets.append({
        "ip": ip,
        "port": 2222,
        "protocol": "ssh",
        "description": "Internal server — SSH access",
    })
