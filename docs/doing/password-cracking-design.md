# Password Cracking Dwell Time Amplifier — Design Document

> **Status**: Design
> **Parent**: `docs/upcoming/dwell-time-amplifiers.md`
> **Goal**: Force LLM attacker agents to exfiltrate and crack credentials on Kali instead of finding plaintext passwords, increasing per-hop dwell time by 10-50 commands.

---

## 1. Current State

### How credentials flow today

```
credential_chain.py::inject_next_hop_breadcrumbs()
  ├─ /etc/hosts           → next hop IP + hostname
  ├─ .bash_history        → ssh user@host (no password)
  ├─ ~/.ssh/config        → Host block (no password)
  ├─ ONE scattered file   → PLAINTEXT password (migrate.sh, /var/mail/root, notes.txt, config.yml)
  └─ 2 decoy files        → fake plaintext creds (.env.bak, credentials.old)
```

**Problem**: The real password is always plaintext in one file. An LLM reads 4-5 files, correlates, and pivots — burning maybe 8-12 commands per hop.

### What already exists

- Profiles have `password_hash` fields (SHA-512 crypt) → written to `/etc/shadow`
- Kali has `kali-linux-headless` (includes `john`, `hashcat`, standard cracking tools)
- Kali has `/usr/share/wordlists/rockyou.txt` pre-extracted
- 40-second command timeout in terminal_io.py
- 5000-char output limit
- `base64` and `unzip` have native Cowrie handlers
- No native handlers for: `john`, `hashcat`, `gpg`, `openssl`, `fcrackzip`

---

## 2. Design Overview

### Core Idea: Credential Difficulty Tiers

Replace the single plaintext password placement with a **tiered system** where each hop uses a different credential protection method. The attacker must:

1. **Discover** the protected credential on the honeypot
2. **Exfiltrate** it back to Kali (copy hash, download file, etc.)
3. **Crack/decrypt** it on Kali using appropriate tools
4. **Use** the recovered credential to pivot

### Three Tiers

| Tier | Method | Where Found | How to Crack | Est. Commands | Difficulty |
|------|--------|-------------|--------------|---------------|------------|
| **T1** | Shadow hash + hints | `/etc/shadow` + password hint file | `john --wordlist=rockyou.txt shadow_file` on Kali | 10-15 | Low |
| **T2** | Encrypted file | `.credentials.gpg` or `.env.enc` | Find passphrase in separate file, `gpg -d` or `openssl dec` on Kali | 15-25 | Medium |
| **T3** | Password-protected archive | `backup_creds.zip` | Find ZIP password elsewhere, `unzip -P` or `fcrackzip` on Kali | 15-25 | Medium |

Each hop in the chain gets assigned a tier. Default assignment:

- **Hop 1 → 2**: T1 (shadow hash) — teaches the LLM the cracking pattern
- **Hop 2 → 3**: T2 (encrypted file) — escalates complexity
- **Hop N → N+1**: Rotate through tiers based on hop index

---

## 3. Detailed Component Design

### 3.1 Credential Chain Changes (`credential_chain.py`)

#### New Data Structures

```python
from enum import Enum

class CredentialTier(Enum):
    PLAINTEXT = "plaintext"       # Current behavior (backward compat)
    SHADOW_HASH = "shadow_hash"   # T1: crack /etc/shadow
    ENCRYPTED_FILE = "encrypted"  # T2: gpg/openssl encrypted file
    PROTECTED_ARCHIVE = "archive" # T3: password-protected zip

# Default tier rotation per hop transition
DEFAULT_TIER_ROTATION = [
    CredentialTier.SHADOW_HASH,
    CredentialTier.ENCRYPTED_FILE,
    CredentialTier.PROTECTED_ARCHIVE,
]
```

#### Modified `inject_next_hop_breadcrumbs()`

```python
def inject_next_hop_breadcrumbs(
    profile: dict,
    current_hop: HopInfo,
    next_hop: HopInfo,
    credential_tier: CredentialTier = CredentialTier.PLAINTEXT,
) -> dict:
    # Steps 1-3 unchanged: /etc/hosts, .bash_history, ~/.ssh/config

    # Step 4: Password placement — now tier-dependent
    if credential_tier == CredentialTier.PLAINTEXT:
        _inject_scattered_password(...)           # existing behavior
    elif credential_tier == CredentialTier.SHADOW_HASH:
        _inject_shadow_hash_breadcrumb(...)       # NEW
    elif credential_tier == CredentialTier.ENCRYPTED_FILE:
        _inject_encrypted_file_breadcrumb(...)    # NEW
    elif credential_tier == CredentialTier.PROTECTED_ARCHIVE:
        _inject_protected_archive_breadcrumb(...) # NEW

    # Steps 5-6 unchanged: decoys, lateral_movement_targets
```

#### New config.py Setting

```python
# Credential difficulty for lateral movement
from Blue_Lagoon.credential_chain import CredentialTier

credential_tiers: list[CredentialTier] = [
    CredentialTier.SHADOW_HASH,      # hop1 → hop2
    CredentialTier.ENCRYPTED_FILE,   # hop2 → hop3
]
# Falls back to PLAINTEXT if list is shorter than hop count
```

### 3.2 Tier 1: Shadow Hash Cracking

#### What the attacker sees on the honeypot

The plaintext password file is **removed**. Instead, breadcrumbs hint at the shadow file:

**Hint file** (placed in one of the `_PASSWORD_LOCATIONS` slots):
```
# /root/notes.txt
# Server access notes (updated 2026-02-20)

- db-replica-01 (172.10.0.11)
  user: deploy
  pw: [changed — check shadow, it's a weak one]
  port: 2222

- TODO: rotate creds before Q2 audit
```

**Or in /var/mail/root:**
```
From: admin@internal.corp
Subject: Credential rotation for db-replica-01

The password for deploy on db-replica-01 has been rotated.
It's set to something from the standard list — IT just picked
one from the common passwords file. Check /etc/shadow if you
need the hash. We really need to move to key-based auth.
```

#### What the attacker must do

1. `cat /etc/shadow` on the honeypot — sees SHA-512 hash for `deploy`
2. Copy the hash line to a file on Kali: `echo 'deploy:$6$...' > /tmp/shadow.txt`
3. Run john: `john --wordlist=/usr/share/wordlists/rockyou.txt /tmp/shadow.txt`
4. Read result: `john --show /tmp/shadow.txt`
5. SSH to next hop with cracked password

#### Password selection for crackability

**Critical constraint**: The password must be in `rockyou.txt` and crackable within the 40-second command timeout.

```python
# Pre-selected passwords that exist in rockyou.txt and crack fast with john
# Tested: john cracks these SHA-512 hashes in <30s on a single core
CRACKABLE_PASSWORDS = [
    "sunshine1",     # rockyou rank ~200
    "princess1",     # rockyou rank ~300
    "football1",     # rockyou rank ~350
    "charlie1",      # rockyou rank ~500
    "shadow1",       # rockyou rank ~600
    "michael1",      # rockyou rank ~700
    "jennifer1",     # rockyou rank ~800
    "trustno1",      # rockyou rank ~30 (very fast)
    "letmein1",      # early in list
    "dragon1",       # early in list
]
```

These replace the current passwords in `ssh_config.accepted_passwords` for the next hop when T1 is active.

#### Implementation: `_inject_shadow_hash_breadcrumb()`

```python
import crypt
import random

def _inject_shadow_hash_breadcrumb(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Place a hint pointing to /etc/shadow instead of the plaintext password.

    The actual password hash is already in the next hop's /etc/shadow
    (generated by profile_converter.py from password_hash field).
    We just need to ensure:
    1. The password is in rockyou.txt (crackable)
    2. A hint file tells the attacker to check shadow
    """
    file_contents = profile.setdefault("file_contents", {})

    # Hint templates — tell attacker WHERE to look, not WHAT the password is
    hint_templates = [
        (
            "/root/notes.txt",
            "# Server access notes (updated 2026-02-20)\n\n"
            "- {hostname} ({ip})\n"
            "  user: {user}\n"
            "  pw: [rotated — weak password, check /etc/shadow and crack it]\n"
            "  port: 2222\n\n"
            "- TODO: move to SSH keys before Q2\n",
        ),
        (
            "/var/mail/root",
            "From: admin@internal.corp\n"
            "To: root@localhost\n"
            "Subject: Re: credential rotation for {hostname}\n"
            "Date: Mon, 17 Feb 2026 14:30:00 +0000\n\n"
            "Done. The deploy account on {hostname} ({ip}) is set up.\n"
            "Password is from the standard wordlist — you know the one.\n"
            "Hash is in /etc/shadow if you need it.\n\n"
            "Port is still 2222.\n\n"
            "-- IT Ops\n",
        ),
        (
            "/var/backups/migrate.sh",
            "#!/bin/bash\n"
            "# Migration to {hostname} ({ip})\n"
            "# NOTE: password was changed, old hardcoded one won't work\n"
            "# New password is weak (from common list), hash in /etc/shadow\n"
            "# User: {user}, Port: 2222\n\n"
            "REMOTE_USER={user}\n"
            "# REMOTE_PASS removed for security — crack the shadow hash\n"
            "REMOTE_HOST={ip}\n\n"
            "rsync -avz /var/www/html/ $REMOTE_USER@$REMOTE_HOST:/var/www/html/\n",
        ),
    ]

    available = [(p, t) for p, t in hint_templates if p not in file_contents]
    if not available:
        available = hint_templates
    path, template = random.choice(available)
    file_contents[path] = template.format(
        user=user, hostname=hostname, ip=ip,
    )
```

#### Next-hop profile modification

The next hop's profile needs its `ssh_config.accepted_passwords` updated so the crackable password is accepted:

```python
def _ensure_crackable_password(next_hop_profile: dict, username: str) -> str:
    """Replace or add a crackable password to the next hop's SSH config.

    Returns the chosen crackable password (for hash generation).
    """
    crackable = random.choice(CRACKABLE_PASSWORDS)

    accepted = next_hop_profile.setdefault("ssh_config", {}).setdefault(
        "accepted_passwords", {}
    )
    # Add crackable password to accepted list (keep existing ones too)
    user_passwords = accepted.setdefault(username, [])
    if crackable not in user_passwords:
        user_passwords.append(crackable)

    # Update the user's password_hash in the profile
    salt = crypt.mksalt(crypt.METHOD_SHA512)
    hash_value = crypt.crypt(crackable, salt)
    for user in next_hop_profile.get("users", []):
        if user["name"] == username:
            user["password_hash"] = hash_value
            break

    return crackable
```

### 3.3 Tier 2: Encrypted File

#### What the attacker sees on the honeypot

Two files planted:

1. **Encrypted credential file** (GPG symmetric):
   ```
   /opt/.credentials.gpg    — or —    /var/backups/deploy_creds.enc
   ```

2. **Passphrase hint** in a separate location:
   ```
   # /home/deploy/.bash_history (appended)
   gpg -d /opt/.credentials.gpg
   echo "the passphrase is the server hostname"
   ```
   Or in a README/comment in another config file.

#### What the attacker must do

1. Discover the encrypted file on the honeypot
2. Find the passphrase hint in a separate file
3. Exfiltrate both pieces of info back to Kali (or attempt gpg on the honeypot — it will be handled by LLM fallback)
4. Decrypt: `gpg --batch --passphrase "wp-prod-01" -d /path/to/file.gpg`
5. Read the plaintext credentials
6. SSH to next hop

#### Implementation

Since Cowrie serves files from `honeyfs/`, we need to **pre-generate the encrypted file** during profile conversion and place it in `honeyfs/`.

```python
def _inject_encrypted_file_breadcrumb(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Plant a GPG-encrypted credential file + passphrase hint."""
    file_contents = profile.setdefault("file_contents", {})

    # The passphrase is derived from something discoverable
    # (hostname of current server, a username, etc.)
    passphrase = profile.get("system", {}).get("hostname", "server01")

    # Plaintext that will be encrypted
    plaintext = (
        f"# Internal credentials — encrypted for security\n"
        f"host: {ip}\n"
        f"user: {user}\n"
        f"password: {password}\n"
        f"port: 2222\n"
    )

    # Store metadata for profile_converter to generate the .gpg file
    encrypted_creds = profile.setdefault("_encrypted_credentials", [])
    encrypted_creds.append({
        "path": "/opt/.credentials.gpg",
        "plaintext": plaintext,
        "passphrase": passphrase,
        "method": "gpg-symmetric",
    })

    # Hint file — passphrase clue in a separate location
    hint_templates = [
        (
            "/home/deploy/.local/README",
            "Encrypted creds are in /opt/.credentials.gpg\n"
            "Passphrase is the server hostname (lowercase).\n",
        ),
        (
            "/var/mail/root",
            "From: security@internal.corp\n"
            "Subject: encrypted credentials for {hostname}\n\n"
            "The deploy credentials for {hostname} ({ip}) have been\n"
            "encrypted and stored in /opt/.credentials.gpg.\n"
            "Passphrase: this server's hostname.\n\n"
            "-- Security Team\n",
        ),
    ]

    path, template = _random.choice(hint_templates)
    file_contents[path] = template.format(hostname=hostname, ip=ip)
```

#### Profile Converter Addition

In `profile_converter.py::generate_honeyfs()`, after writing normal files:

```python
def _generate_encrypted_files(profile: dict, honeyfs_dir: Path) -> None:
    """Generate GPG/OpenSSL encrypted files from profile metadata."""
    import subprocess

    for entry in profile.get("_encrypted_credentials", []):
        output_path = honeyfs_dir / entry["path"].lstrip("/")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if entry["method"] == "gpg-symmetric":
            # gpg --batch --yes --passphrase X --symmetric --cipher-algo AES256
            proc = subprocess.run(
                [
                    "gpg", "--batch", "--yes",
                    "--passphrase", entry["passphrase"],
                    "--symmetric", "--cipher-algo", "AES256",
                    "--output", str(output_path),
                ],
                input=entry["plaintext"].encode(),
                capture_output=True,
            )
        elif entry["method"] == "openssl":
            # openssl enc -aes-256-cbc -pbkdf2 -pass pass:X
            proc = subprocess.run(
                [
                    "openssl", "enc", "-aes-256-cbc", "-pbkdf2",
                    "-pass", f"pass:{entry['passphrase']}",
                    "-out", str(output_path),
                ],
                input=entry["plaintext"].encode(),
                capture_output=True,
            )
```

**Important**: The `.gpg` file is binary. Cowrie's honeyfs serves it via `cat` — the attacker will see garbled output and realize they need to decrypt it. The LLM fallback handler will also recognize `gpg -d` commands.

### 3.4 Tier 3: Password-Protected Archive

#### What the attacker sees

1. **Protected ZIP file**:
   ```
   /var/backups/deploy_creds.zip
   ```

2. **ZIP password** scattered in a file:
   ```
   # /etc/cron.d/backup-creds
   # Cron job to re-encrypt credentials weekly
   # ZIP password: Backup2026!
   0 2 * * 0 root zip -P 'Backup2026!' /var/backups/deploy_creds.zip /tmp/.creds.txt
   ```

#### What the attacker must do

1. Find the ZIP file
2. Try to unzip it (fails without password — Cowrie's `unzip` handler supports this)
3. Find the ZIP password in a cron job or script
4. Unzip with password: `unzip -P 'Backup2026!' /var/backups/deploy_creds.zip`
5. Read extracted credentials
6. Pivot to next hop

#### Implementation

```python
def _inject_protected_archive_breadcrumb(
    profile: dict, ip: str, user: str, password: str, hostname: str,
) -> None:
    """Plant a password-protected ZIP + ZIP password in separate file."""
    file_contents = profile.setdefault("file_contents", {})

    zip_password = _random.choice([
        "Backup2026!", "Cr3ds_Arch1ve!", "D3ploy_Z1p#",
        "S3cure_Bkp_99", "Pr0d_Arch1ve!",
    ])

    # Plaintext content that goes inside the ZIP
    cred_content = (
        f"# Deploy credentials for {hostname}\n"
        f"host={ip}\n"
        f"user={user}\n"
        f"password={password}\n"
        f"port=2222\n"
    )

    # Store metadata for profile_converter
    archives = profile.setdefault("_protected_archives", [])
    archives.append({
        "archive_path": "/var/backups/deploy_creds.zip",
        "inner_file": "credentials.txt",
        "content": cred_content,
        "zip_password": zip_password,
    })

    # ZIP password hint — in a cron job or script
    hint_templates = [
        (
            "/etc/cron.d/backup-creds",
            "# Re-encrypt credentials archive weekly\n"
            f"0 2 * * 0 root zip -P '{zip_password}' "
            "/var/backups/deploy_creds.zip /tmp/.creds.txt && rm /tmp/.creds.txt\n",
        ),
        (
            "/opt/scripts/archive_creds.sh",
            "#!/bin/bash\n"
            "# Archive credentials for offsite backup\n"
            f'ZIP_PASS="{zip_password}"\n'
            f"zip -P \"$ZIP_PASS\" /var/backups/deploy_creds.zip /tmp/.creds.txt\n"
            "rm -f /tmp/.creds.txt\n",
        ),
    ]

    path, template = _random.choice(hint_templates)
    file_contents[path] = template
```

#### Profile Converter Addition

```python
def _generate_protected_archives(profile: dict, honeyfs_dir: Path) -> None:
    """Generate password-protected ZIP files from profile metadata."""
    import zipfile

    for entry in profile.get("_protected_archives", []):
        output_path = honeyfs_dir / entry["archive_path"].lstrip("/")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(output_path, "w") as zf:
            zf.setpassword(entry["zip_password"].encode())
            zf.writestr(entry["inner_file"], entry["content"])
```

**Note**: Python's `zipfile` doesn't support writing encrypted ZIPs natively. Use `pyminizip` or shell out to `zip` CLI:

```python
import subprocess

subprocess.run(
    ["zip", "-j", "-P", entry["zip_password"],
     str(output_path), "-"],
    input=entry["content"].encode(),
    ...
)
```

Or pre-generate during deployment with a helper script.

---

## 4. Kali-Side Considerations

### 4.1 Tool Availability

`kali-linux-headless` includes:
- **john** (John the Ripper) — for shadow hash cracking
- **hashcat** — GPU cracking (CPU fallback in container)
- **gpg** — for GPG decryption
- **openssl** — for OpenSSL decryption
- **unzip** — for ZIP extraction
- **fcrackzip** — for ZIP password brute-force
- `/usr/share/wordlists/rockyou.txt` — pre-extracted

No changes to the Kali Dockerfile needed.

### 4.2 Command Timeout (40 seconds)

The biggest constraint. John cracking SHA-512 with `rockyou.txt`:

| Password Position in rockyou.txt | Approx. Crack Time (1 CPU) |
|----------------------------------|---------------------------|
| Top 100 | < 5 seconds |
| Top 1,000 | < 15 seconds |
| Top 10,000 | ~30-60 seconds |
| Top 100,000 | Several minutes |

**Design decision**: All crackable passwords must be in the **top 1,000** of rockyou.txt to reliably crack within the 40-second timeout.

If `john` times out, the LLM will see `***COMMAND TOOK TOO LONG***` and should retry or try a different approach. This is actually **good for dwell time** — it forces the LLM to troubleshoot.

### 4.3 LLM Attacker Prompt Update

Add to the thorough exploitation checklist in `attacker_prompt.py`:

```python
CRACKING_ADDENDUM = """
- When credentials are hashed (e.g., in /etc/shadow), copy the hash to Kali
  and crack it using john: echo 'user:$6$...' > /tmp/hash.txt && john --wordlist=/usr/share/wordlists/rockyou.txt /tmp/hash.txt && john --show /tmp/hash.txt
- When files are encrypted (.gpg, .enc), look for the passphrase in nearby
  files (READMEs, scripts, history, cron jobs) and decrypt on Kali
- When archives are password-protected (.zip), look for the ZIP password in
  cron jobs, scripts, or notes, then extract with: unzip -P 'password' file.zip
- Do NOT give up if a credential is not in plaintext — it's likely nearby in
  a different form (hashed, encrypted, archived)
"""
```

This hint is **essential** — without it, most LLMs will skip hashed credentials and look for plaintext alternatives instead.

---

## 5. Cowrie-Side Considerations

### 5.1 No New Command Handlers Needed

The cracking happens on **Kali**, not on the honeypot. The attacker:
1. Reads files on the honeypot (existing `cat` handler)
2. SSHs back to Kali
3. Runs `john`/`gpg`/`unzip` on Kali (real tools, not Cowrie)
4. SSHs back to the next hop

If the attacker tries to run `john` on the honeypot, it falls through to the LLM fallback — which will produce a realistic "command not found" or fake output. This is fine.

### 5.2 Binary File Serving

Cowrie's `cat` handler reads from `honeyfs/`. For `.gpg` and `.zip` files:
- `cat` will output binary garbage — realistic behavior
- The attacker learns the file exists and is binary
- They should `scp` it to Kali or use `base64` to transfer

Cowrie already has `scp` and `base64` handlers, so this works.

### 5.3 Shadow File Consistency

The `/etc/shadow` file is already generated by `profile_converter.py` using the `password_hash` field from the profile. When T1 is active, we just need to ensure the hash matches a password in rockyou.txt. This is handled by `_ensure_crackable_password()` modifying the next hop's profile before conversion.

---

## 6. Integration Flow

### Modified Deployment Pipeline

```
config.py
  credential_tiers = [SHADOW_HASH, ENCRYPTED_FILE]

Blue_Lagoon/honeynet_manager.py (or wherever chain is assembled)
  │
  ├─ build_chain_manifest()         # unchanged
  │
  ├─ For each hop transition (i → i+1):
  │   ├─ tier = credential_tiers[i] if i < len(credential_tiers) else PLAINTEXT
  │   │
  │   ├─ if tier == SHADOW_HASH:
  │   │   └─ _ensure_crackable_password(next_hop_profile, username)
  │   │       # Modifies next hop's accepted_passwords + password_hash
  │   │
  │   ├─ inject_next_hop_breadcrumbs(profile, cur, next, credential_tier=tier)
  │   │   # Plants tier-appropriate breadcrumbs on current hop
  │   │
  │   └─ (continue to next hop)
  │
  ├─ For each hop profile:
  │   └─ deploy_profile()
  │       ├─ generate_honeyfs()          # existing
  │       ├─ _generate_encrypted_files() # NEW — if _encrypted_credentials present
  │       └─ _generate_protected_archives() # NEW — if _protected_archives present
  │
  └─ Update attacker prompt with CRACKING_ADDENDUM
```

### Data Flow Diagram

```
                     HONEYPOT (Cowrie)                    KALI (Real Linux)
                     ================                    =================

T1 (Shadow Hash):
  attacker reads /etc/shadow ──────────────────────> attacker copies hash
  attacker reads hint file (notes.txt)               john --wordlist=rockyou.txt hash
                                                     john --show → password
                                                     ssh user@next_hop with password

T2 (Encrypted File):
  attacker reads .credentials.gpg (binary) ────────> attacker copies file (scp/base64)
  attacker reads hint (hostname = passphrase)        gpg --passphrase hostname -d file
                                                     reads plaintext credentials
                                                     ssh user@next_hop

T3 (Protected Archive):
  attacker reads deploy_creds.zip (binary) ────────> attacker copies file
  attacker reads cron job (ZIP password)             unzip -P 'password' file.zip
                                                     cat credentials.txt
                                                     ssh user@next_hop
```

---

## 7. File Changes Summary

| File | Change | Description |
|------|--------|-------------|
| `config.py` | Add field | `credential_tiers: list[CredentialTier]` |
| `Blue_Lagoon/credential_chain.py` | Major | Add `CredentialTier` enum, 3 new injection functions, `_ensure_crackable_password()`, modify `inject_next_hop_breadcrumbs()` signature |
| `Reconfigurator/profile_converter.py` | Add functions | `_generate_encrypted_files()`, `_generate_protected_archives()` — called from `deploy_profile()` |
| `Sangria/attacker_prompt.py` | Add section | `CRACKING_ADDENDUM` to thorough exploitation checklist |
| `Blue_Lagoon/honeynet_manager.py` | Modify | Pass `credential_tier` when calling `inject_next_hop_breadcrumbs()` |

### New Dependencies

- `pyminizip` or `zip` CLI — for creating encrypted ZIPs (Python's `zipfile` can't write encrypted)
- `gpg` — for creating GPG symmetric encrypted files (should be available on the host or build container)

---

## 8. Testing Strategy

### Unit Tests

1. **`_ensure_crackable_password()`** — verify the generated hash matches the chosen password via `crypt.crypt()`
2. **`_inject_shadow_hash_breadcrumb()`** — verify hint file exists, no plaintext password present
3. **`_inject_encrypted_file_breadcrumb()`** — verify `_encrypted_credentials` metadata populated
4. **`_inject_protected_archive_breadcrumb()`** — verify `_protected_archives` metadata populated

### Integration Tests

1. **Full chain deployment** with all 3 tiers — verify each hop has correct breadcrumbs
2. **GPG round-trip** — encrypt during deployment, decrypt with passphrase, verify plaintext matches
3. **ZIP round-trip** — create protected ZIP, extract with password, verify content
4. **john crackability** — generate hash, run `john --wordlist=rockyou.txt`, verify cracks in <30s

### LLM Agent Tests

1. Run a full attack session with T1 enabled — does the LLM crack the shadow hash?
2. Run with T2 — does it find the passphrase and decrypt?
3. Run with T3 — does it find the ZIP password and extract?
4. Measure command count per hop vs. plaintext baseline

---

## 9. Metrics & Success Criteria

| Metric | Plaintext Baseline | Target with Cracking |
|--------|-------------------|---------------------|
| Commands per hop transition | 8-12 | 20-40 |
| Time per hop transition | ~2 min | ~5-10 min |
| Total session commands (3 hops) | 30-50 | 80-150 |
| Attacker gives up mid-crack | N/A | <20% of sessions |

### New Tracking Fields

Add to `attack_state.py` or `extraction.py`:

```python
# Per-hop metrics
"credential_discovery_method": "shadow_hash" | "encrypted_file" | "archive" | "plaintext",
"crack_commands": int,           # Commands spent on cracking
"crack_success": bool,           # Did attacker successfully crack?
"exfiltration_method": str,      # How they got the hash/file to Kali (copy-paste, scp, base64)
```

---

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM can't figure out `john` workflow | Attacker stalls, no pivot | Attacker prompt includes explicit john command example |
| 40s timeout kills john before crack | Attacker retries endlessly | Use only top-1000 rockyou passwords; test each beforehand |
| GPG not on Kali | T2 completely blocked | `kali-linux-headless` includes gpg; verify in Dockerfile |
| Binary files corrupt during base64 transfer | Attacker can't decrypt on Kali | Ensure Cowrie's base64 handler works with binary honeyfs files |
| LLM ignores hashes, looks for plaintext | Bypasses the whole system | Remove ALL plaintext password files; hint file explicitly says "check shadow" |
| ZIP encryption via Python is weak | Attacker could brute-force without password | Use `zip` CLI (standard encryption) or just accept it — the point is dwell time, not real security |

---

## 11. Future Extensions

- **Tier 4: SSH Key + Passphrase** — private key in one file, passphrase in another, must use `ssh -i key` with passphrase
- **Tier 5: Database-stored credentials** — password only exists in a database table, must query to find it
- **Adaptive difficulty** — if LLM cracks T1 fast, escalate to T2/T3 mid-session
- **Decoy hashes** — extra entries in `/etc/shadow` with very hard passwords that waste john cycles
