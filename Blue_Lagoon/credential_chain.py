"""Credential chain management for multi-hop HoneyNet deployments.

Builds a chain manifest mapping each hop's IP, credentials, and hostname,
then injects breadcrumbs pointing to the next hop into each profile.
"""

from __future__ import annotations

import copy
import crypt
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Credential difficulty tiers
# ---------------------------------------------------------------------------

class CredentialTier(Enum):
    PLAINTEXT = "plaintext"        # Current behavior (backward compat)
    SHADOW_HASH = "shadow_hash"    # T1: crack /etc/shadow on Kali
    ENCRYPTED_FILE = "encrypted"   # T2: gpg-encrypted credential file
    PROTECTED_ARCHIVE = "archive"  # T3: password-protected ZIP


# Passwords confirmed to be in the top ~1000 of rockyou.txt so john can
# crack the SHA-512 hash within the 40-second terminal timeout.
CRACKABLE_PASSWORDS = [
    "sunshine1",
    "princess1",
    "football1",
    "charlie1",
    "shadow1",
    "michael1",
    "jennifer1",
    "trustno1",
    "letmein1",
    "dragon1",
]


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
    credential_tier: CredentialTier = CredentialTier.PLAINTEXT,
) -> dict:
    """Inject real next-hop credentials into the profile, scattered across files.

    The credentials are split so the attacker must correlate multiple files:
    - /etc/hosts: hostname mapping (host + IP)
    - .bash_history: SSH commands with username + host (no password)
    - ~/.ssh/config: Host block with username + host (no password)
    - Password: placed according to *credential_tier* (plaintext, shadow hash,
      encrypted file, or protected archive)
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

    # --- 4. Password placement — tier-dependent ---
    if credential_tier == CredentialTier.SHADOW_HASH:
        _inject_shadow_hash_breadcrumb(profile, next_ip, next_user, next_pass, next_host)
    elif credential_tier == CredentialTier.ENCRYPTED_FILE:
        _inject_encrypted_file_breadcrumb(profile, next_ip, next_user, next_pass, next_host)
    elif credential_tier == CredentialTier.PROTECTED_ARCHIVE:
        _inject_protected_archive_breadcrumb(profile, next_ip, next_user, next_pass, next_host)
    else:
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


# ---------------------------------------------------------------------------
# Tier 1: Shadow hash breadcrumbs
# ---------------------------------------------------------------------------

_SHADOW_HINT_TEMPLATES = [
    (
        "/root/notes.txt",
        "# Server access notes (updated 2026-02-20)\n\n"
        "- {hostname} ({ip})\n"
        "  user: {user}\n"
        "  pw: check /etc/shadow on THIS server for {user}'s hash — crack it on Kali\n"
        "  port: 2222\n\n"
        "Steps:\n"
        "  1. cat /etc/shadow | grep {user}\n"
        "  2. Copy the hash line, exit to Kali\n"
        "  3. echo '<hash line>' > /tmp/hash.txt\n"
        "  4. john --wordlist=/usr/share/wordlists/rockyou.txt /tmp/hash.txt\n"
        "  5. ssh {user}@{ip} -p 2222\n",
    ),
    (
        "/var/mail/root",
        "From: admin@internal.corp\n"
        "To: root@localhost\n"
        "Subject: Re: credential rotation for {hostname}\n"
        "Date: Mon, 17 Feb 2026 14:30:00 +0000\n\n"
        "Done. The {user} account on {hostname} ({ip}:2222) is set up.\n"
        "Password was synced from rockyou — {user}'s hash is in /etc/shadow\n"
        "on this server. Crack it on Kali with john, then:\n"
        "  ssh {user}@{ip} -p 2222\n\n"
        "-- IT Ops\n",
    ),
    (
        "/var/backups/migrate.sh",
        "#!/bin/bash\n"
        "# Migration to {hostname} ({ip})\n"
        "# NOTE: password was changed, old hardcoded one won't work\n"
        "# {user}'s hash is in /etc/shadow on this server (weak rockyou password)\n"
        "# Crack it on Kali, then: ssh {user}@{ip} -p 2222\n\n"
        "REMOTE_USER={user}\n"
        "# REMOTE_PASS removed for security — crack {user}'s shadow hash\n"
        "REMOTE_HOST={ip}\n\n"
        "rsync -avz /var/www/html/ $REMOTE_USER@$REMOTE_HOST:/var/www/html/\n",
    ),
]


def _inject_shadow_hash_breadcrumb(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Inject a crackable hash into *this* hop's /etc/shadow + place a hint.

    The attacker reads /etc/shadow on the current hop, finds the hash for
    the next-hop user, exits to Kali, cracks it with john, then SSHes to
    the next hop.

    If the next-hop user already exists in this hop's users list (e.g.
    both hops have ``root``), we replace the existing password_hash so
    /etc/shadow contains only ONE entry for that user — the crackable one.
    Otherwise we add an ``_extra_shadow_entries`` entry.
    """
    # Generate a crackable SHA-512 hash for the next-hop password
    salt = crypt.mksalt(crypt.METHOD_SHA512)
    crackable_hash = crypt.crypt(password, salt)

    # Try to replace an existing user's hash in the current profile
    replaced = False
    for u in profile.get("users", []):
        if u["name"] == user:
            u["password_hash"] = crackable_hash
            replaced = True
            break

    if not replaced:
        extra = profile.setdefault("_extra_shadow_entries", [])
        extra.append({"username": user, "hash": crackable_hash})

    # Place hint file
    file_contents = profile.setdefault("file_contents", {})

    available = [(p, t) for p, t in _SHADOW_HINT_TEMPLATES if p not in file_contents]
    if not available:
        available = list(_SHADOW_HINT_TEMPLATES)
    path, template = _random.choice(available)
    file_contents[path] = template.format(user=user, hostname=hostname, ip=ip)


def ensure_crackable_password(next_hop_profile: dict, username: str) -> str:
    """Replace or add a crackable password to the next hop's SSH config.

    Picks a password from ``CRACKABLE_PASSWORDS`` (all in the top ~1000 of
    rockyou.txt), updates ``ssh_config.accepted_passwords`` and the user's
    ``password_hash`` so the generated /etc/shadow is consistent.

    Returns the chosen crackable password.
    """
    crackable = _random.choice(CRACKABLE_PASSWORDS)

    accepted = next_hop_profile.setdefault("ssh_config", {}).setdefault(
        "accepted_passwords", {},
    )
    # Replace all existing passwords so the old plaintext ones no longer work
    accepted[username] = [crackable]

    # Update the user's password_hash so /etc/shadow is crackable
    salt = crypt.mksalt(crypt.METHOD_SHA512)
    hash_value = crypt.crypt(crackable, salt)
    for u in next_hop_profile.get("users", []):
        if u["name"] == username:
            u["password_hash"] = hash_value
            break

    return crackable


_COMMON_PASSWORDS = {
    "root", "toor", "123456", "password", "admin", "admin123",
    "root123", "test", "guest", "oracle", "postgres", "jenkins",
    "changeme", "letmein", "welcome", "monkey", "dragon", "master",
}

# Non-guessable passwords for T2/T3 tiers (hidden inside GPG/ZIP files)
_TIER_PASSWORDS = [
    "xK9v#mR2pL!", "Qw8$nT5jB3@", "fH7&yU4cZ6*",
    "aP3!eW9dN1%", "bV6^kS2gM8+", "rJ5#tL7hX4!",
]


def lock_down_hop_passwords(
    next_hop_profile: dict, username: str, password: str,
) -> str:
    """Replace all accepted passwords for *username* with a non-guessable one.

    If *password* is a common/guessable value (root, 123456, etc.), it is
    replaced with a random strong password.  The chosen password is returned
    so the caller can update HopInfo and inject it into breadcrumbs.

    Also removes passwords for OTHER users so the attacker can't bypass
    the tier by guessing a different account.
    """
    if password.lower() in _COMMON_PASSWORDS:
        password = _random.choice(_TIER_PASSWORDS)

    accepted = next_hop_profile.setdefault("ssh_config", {}).setdefault(
        "accepted_passwords", {},
    )
    # Only the tier-specific user/password pair is valid
    accepted[username] = [password]
    # Remove all other users' passwords — only the intended user works
    for other_user in list(accepted):
        if other_user != username:
            del accepted[other_user]

    return password


# ---------------------------------------------------------------------------
# Tier 2: GPG-encrypted credential file
# ---------------------------------------------------------------------------

_ENCRYPTED_HINT_TEMPLATES = [
    (
        "/root/notes.txt",
        "# Credential notes (updated 2026-02-18)\n\n"
        "SSH creds for {hostname} ({ip}) are stored in /opt/.credentials.gpg\n"
        "Read with: cat /opt/.credentials.gpg\n"
        "Use the user/password/port to connect:\n"
        "  ssh <user>@{ip} -p 2222\n",
    ),
    (
        "/var/mail/root",
        "From: security@internal.corp\n"
        "To: root@localhost\n"
        "Subject: credentials for {hostname}\n"
        "Date: Mon, 17 Feb 2026 10:45:00 +0000\n\n"
        "The SSH credentials for {hostname} ({ip}:2222) are in\n"
        "/opt/.credentials.gpg — read with cat and use them.\n\n"
        "-- Security Team\n",
    ),
    (
        "/var/backups/README",
        "Deploy credentials: /opt/.credentials.gpg\n"
        "Contains SSH user/password/host/port for {hostname}.\n",
    ),
]


def _inject_encrypted_file_breadcrumb(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Plant metadata for a GPG-encrypted credential file + passphrase hint.

    The actual .gpg file is generated later by profile_converter.py from the
    ``_encrypted_credentials`` list stored on the profile dict.
    """
    file_contents = profile.setdefault("file_contents", {})

    # Passphrase = current server's hostname (discoverable via `hostname`)
    current_hostname = profile.get("system", {}).get("hostname", "server01")

    plaintext = (
        f"# Internal credentials — encrypted for security\n"
        f"host: {ip}\n"
        f"user: {user}\n"
        f"password: {password}\n"
        f"port: 2222\n"
    )

    # Store credentials directly in file_contents so Cowrie can serve them.
    # The file appears in directory listings and is readable via `cat`.
    gpg_path = "/opt/.credentials.gpg"
    file_contents[gpg_path] = plaintext

    available = [(p, t) for p, t in _ENCRYPTED_HINT_TEMPLATES if p not in file_contents]
    if not available:
        available = list(_ENCRYPTED_HINT_TEMPLATES)
    path, template = _random.choice(available)
    file_contents[path] = template.format(hostname=hostname, ip=ip)


# ---------------------------------------------------------------------------
# Tier 3: Password-protected ZIP archive
# ---------------------------------------------------------------------------

_ZIP_PASSWORDS = [
    "Backup2026!", "Cr3ds_Arch1ve!", "D3ploy_Z1p#",
    "S3cure_Bkp_99", "Pr0d_Arch1ve!",
]

_ZIP_HINT_TEMPLATES = [
    (
        "/etc/cron.d/backup-creds",
        "# Credential archive for {hostname} ({ip})\n"
        "# SSH creds stored at /var/backups/deploy_creds.zip\n"
        "# Read with: cat /var/backups/deploy_creds.zip\n"
        "# Then: ssh {user}@{ip} -p 2222\n"
        "0 2 * * 0 root /opt/scripts/archive_creds.sh\n",
    ),
    (
        "/root/notes.txt",
        "# Deploy credentials (updated 2026-02-14)\n\n"
        "SSH creds for {hostname} ({ip}) are in /var/backups/deploy_creds.zip\n"
        "Read with: cat /var/backups/deploy_creds.zip\n"
        "Then connect: ssh {user}@{ip} -p 2222\n",
    ),
    (
        "/var/mail/root",
        "From: devops@internal.corp\n"
        "To: root@localhost\n"
        "Subject: credentials for {hostname}\n"
        "Date: Fri, 14 Feb 2026 16:20:00 +0000\n\n"
        "SSH credentials for {hostname} ({ip}:2222) saved to\n"
        "/var/backups/deploy_creds.zip — read with cat and use them.\n\n"
        "-- DevOps\n",
    ),
]


def _inject_protected_archive_breadcrumb(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Plant a credential file at /var/backups/deploy_creds.zip + hint.

    The file is stored as plaintext in file_contents (readable via ``cat``).
    The challenge is discovery — finding the file and correlating with the hint.
    """
    file_contents = profile.setdefault("file_contents", {})

    cred_content = (
        f"# Deploy credentials for {hostname}\n"
        f"host={ip}\n"
        f"user={user}\n"
        f"password={password}\n"
        f"port=2222\n"
    )

    zip_path = "/var/backups/deploy_creds.zip"
    file_contents[zip_path] = cred_content

    available = [(p, t) for p, t in _ZIP_HINT_TEMPLATES if p not in file_contents]
    if not available:
        available = list(_ZIP_HINT_TEMPLATES)
    path, template = _random.choice(available)
    file_contents[path] = template.format(hostname=hostname, ip=ip, user=user)
