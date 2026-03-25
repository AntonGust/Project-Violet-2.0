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
    attack_ip: str          # IP on the shared net_attack network (reachable from Kali)
    internal_ip: str        # IP on the hop's internal network (for profile realism)
    internal_subnet: str    # Internal network subnet (e.g. "10.0.1.0/24")
    ssh_port: int            # always 2222
    username: str            # SSH user for this hop
    password: str            # SSH password for this hop
    hostname: str            # from profile system.hostname
    profile_path: str

    @property
    def ip_from_prev(self) -> str:
        """Backwards-compatible alias — breadcrumbs now use attack_ip."""
        return self.attack_ip


@dataclass
class ChainManifest:
    hops: list[HopInfo]
    run_id: str


# Internal subnets for per-hop realism (what the profile's /etc/hosts etc. show)
_INTERNAL_SUBNETS = [
    ("10.0.1.0/24", "10.0.1.15"),
    ("10.0.3.0/24", "10.0.3.10"),
    ("10.0.2.0/24", "10.0.2.7"),
    ("10.0.4.0/24", "10.0.4.20"),
    ("10.0.5.0/24", "10.0.5.12"),
]


def build_chain_manifest(run_id: str, chain_profiles: list[str]) -> ChainManifest:
    """Load each profile and build the chain manifest with IPs and credentials.

    Star topology — all hops are on a shared net_attack network:
    - Kali:  172.{run_id}.0.2
    - Pot1:  172.{run_id}.0.10
    - Pot2:  172.{run_id}.0.11
    - Pot3:  172.{run_id}.0.12
    - PotN:  172.{run_id}.0.{10+N-1}

    Each hop also gets an internal network for profile realism.
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

        # All hops on the shared attack network
        attack_ip = f"172.{run_id}.0.{10 + i}"

        # Internal network for profile realism
        if i < len(_INTERNAL_SUBNETS):
            internal_subnet, internal_ip = _INTERNAL_SUBNETS[i]
        else:
            internal_subnet = f"10.0.{i + 1}.0/24"
            internal_ip = f"10.0.{i + 1}.15"

        hops.append(HopInfo(
            hop_index=i,
            attack_ip=attack_ip,
            internal_ip=internal_ip,
            internal_subnet=internal_subnet,
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
    """Inject real next-hop credentials into the profile, scattered across files.

    The credentials are split so the attacker must correlate multiple files:
    - /etc/hosts: hostname mapping (host + IP)
    - .bash_history: SSH commands with username + host (no password)
    - ~/.ssh/config: Host block with username + host (no password)
    - Scattered password: placed in a realistic location (backup script, mail, notes)
    - Decoy credentials: 2 fake credential sets in other files

    Returns the modified profile (also mutates in-place).
    """
    next_ip = next_hop.ip_from_prev
    next_user = next_hop.username
    next_pass = next_hop.password
    next_host = next_hop.hostname
    next_port = next_hop.ssh_port

    # --- 1. /etc/hosts — hostname mapping ---
    _inject_etc_hosts(profile, next_ip, next_host)

    # --- 2. .bash_history — SSH commands WITHOUT password (user must find it elsewhere) ---
    _inject_bash_history_no_password(profile, next_ip, next_user, next_port)

    # --- 3. ~/.ssh/config — Host block (no password) ---
    _inject_ssh_config(profile, next_ip, next_user, next_host, next_port)

    # --- 4. Password in a realistic scattered location ---
    _inject_scattered_password(profile, next_ip, next_user, next_pass, next_host)

    # --- 5. Decoy credentials (look real but fail) ---
    _inject_decoy_credentials(profile, next_ip, next_host)

    # --- 6. lateral_movement_targets ---
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


def _inject_bash_history_no_password(profile: dict, ip: str, user: str, port: int) -> None:
    """Add SSH commands to .bash_history WITHOUT the password.

    The attacker must find the password in a separate file.
    """
    file_contents = profile.setdefault("file_contents", {})

    home = "/root"
    for u in profile.get("users", []):
        if u.get("name") == "root":
            home = u.get("home", "/root")
            break

    history_path = f"{home}/.bash_history"
    history = file_contents.get(history_path, "")

    if history and not history.endswith("\n"):
        history += "\n"

    new_entries = [
        f"ssh {user}@{ip} -p {port}",
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


import random as _random


# Realistic locations where a password might be found, per profile type
_PASSWORD_LOCATIONS = [
    # (path, template) — {user}, {password}, {host}, {ip} are interpolated
    (
        "/var/backups/migrate.sh",
        "#!/bin/bash\n"
        "# Migration script - last run 2026-02-18\n"
        "# Transfers data to {hostname}\n\n"
        "REMOTE_USER={user}\n"
        "REMOTE_PASS=\"{password}\"\n"
        "REMOTE_HOST={ip}\n\n"
        "rsync -avz /var/www/html/ $REMOTE_USER@$REMOTE_HOST:/var/www/html/\n",
    ),
    (
        "/var/mail/root",
        "From: admin@internal.corp\n"
        "To: root@localhost\n"
        "Subject: Credential rotation for {hostname}\n"
        "Date: Tue, 18 Feb 2026 09:12:00 +0000\n\n"
        "Hi,\n\n"
        "The new credentials for {hostname} ({ip}) are:\n"
        "  User: {user}\n"
        "  Pass: {password}\n\n"
        "Please update your configs.\n\n"
        "-- IT Operations\n",
    ),
    (
        "/root/notes.txt",
        "# Server access notes (updated 2026-02-20)\n\n"
        "- {hostname} ({ip})\n"
        "  user: {user}\n"
        "  pw: {password}\n"
        "  port: 2222\n\n"
        "- TODO: rotate creds before Q2 audit\n",
    ),
    (
        "/opt/deploy/config.yml",
        "# Deployment configuration\n"
        "targets:\n"
        "  - name: {hostname}\n"
        "    host: {ip}\n"
        "    port: 2222\n"
        "    ssh_user: {user}\n"
        "    ssh_password: \"{password}\"\n"
        "    deploy_path: /var/www/html\n",
    ),
]

# Decoy credential sets — look real but will fail authentication
_DECOY_USERS = ["admin", "deployer", "backup", "svc-monitor", "jenkins", "ansible"]
_DECOY_PASSWORDS = [
    "Ch@ng3M3_2025!", "Pr0d_Acc3ss#88", "T3mp0rary_P@ss!",
    "B@ckup_S3cur3_99", "Old_Admin_P@ss!", "R0tat3d_Cr3d_Q1!",
]


def _inject_scattered_password(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Place the real password in a single realistic file (not /opt/.env).

    The attacker must find and correlate this with the username from .bash_history.
    """
    file_contents = profile.setdefault("file_contents", {})
    dir_tree = profile.setdefault("directory_tree", {})

    # Pick a random location that doesn't already exist in the profile
    available = [
        (path, tmpl) for path, tmpl in _PASSWORD_LOCATIONS
        if path not in file_contents
    ]
    if not available:
        available = _PASSWORD_LOCATIONS  # fallback: overwrite

    path, template = _random.choice(available)
    content = template.format(user=user, password=password, hostname=hostname, ip=ip)

    file_contents[path] = content

    # Ensure the file appears in directory_tree
    parent = "/".join(path.split("/")[:-1]) or "/"
    filename = path.split("/")[-1]
    entries = dir_tree.setdefault(parent, [])
    if not any(e.get("name") == filename for e in entries):
        entries.append({
            "name": filename,
            "type": "file",
            "permissions": "0640",
            "owner": "root",
            "group": "root",
            "size": len(content),
        })


def _inject_decoy_credentials(profile: dict, real_ip: str, real_hostname: str) -> None:
    """Inject 2 fake credential sets that look plausible but won't work.

    These increase attacker dwell time and create CHeaT detection opportunities.
    """
    file_contents = profile.setdefault("file_contents", {})
    dir_tree = profile.setdefault("directory_tree", {})

    decoy_user1 = _random.choice(_DECOY_USERS)
    decoy_pass1 = _random.choice(_DECOY_PASSWORDS)
    decoy_user2 = _random.choice([u for u in _DECOY_USERS if u != decoy_user1])
    decoy_pass2 = _random.choice([p for p in _DECOY_PASSWORDS if p != decoy_pass1])

    # Decoy 1: old config file with expired-looking credentials
    decoy1_path = "/opt/.env.bak"
    decoy1_content = (
        f"# OLD CONFIG — migrated 2025-11-03, DO NOT USE IN PROD\n"
        f"INTERNAL_HOST={real_ip}\n"
        f"INTERNAL_SSH_USER={decoy_user1}\n"
        f"INTERNAL_SSH_PASS={decoy_pass1}\n"
        f"INTERNAL_SSH_PORT=2222\n"
        f"INTERNAL_HOSTNAME={real_hostname}\n"
    )
    file_contents[decoy1_path] = decoy1_content

    opt_entries = dir_tree.setdefault("/opt", [])
    if not any(e.get("name") == ".env.bak" for e in opt_entries):
        opt_entries.append({
            "name": ".env.bak",
            "type": "file",
            "permissions": "0644",
            "owner": "root",
            "group": "root",
            "size": len(decoy1_content),
        })

    # Decoy 2: credentials file in /var/backups
    decoy2_path = "/var/backups/credentials.old"
    decoy2_content = (
        f"# Backup of credentials — rotated 2025-12-01\n"
        f"# {real_hostname} access\n"
        f"user={decoy_user2}\n"
        f"password={decoy_pass2}\n"
        f"host={real_ip}\n"
        f"port=2222\n"
    )
    file_contents[decoy2_path] = decoy2_content

    backup_entries = dir_tree.setdefault("/var/backups", [])
    if not any(e.get("name") == "credentials.old" for e in backup_entries):
        backup_entries.append({
            "name": "credentials.old",
            "type": "file",
            "permissions": "0600",
            "owner": "root",
            "group": "root",
            "size": len(decoy2_content),
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
