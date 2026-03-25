# Honeynet Fixes Implementation Plan

**Date:** 2026-03-24
**Source:** Diagnostic analysis of `logs/Testing_2026-03-24T17_15_29`
**Status:** Doing

---

## Overview

Six issues identified from the test run. This plan addresses all of them with concrete code changes, ordered by implementation dependency (not priority).

---

## Fix 1: Expand CHeaT Defenses to All Hops

### Problem
CHeaT defenses (unicode honeytokens, canary URLs, prompt traps) are only applied to **hop 0 (entry point)** in honeynet mode. The attacker reached hops 2 and 3 with zero detection coverage. Only 1 unicode token was planted across the entire chain, and `canary_urls`, `prompt_traps`, and `tool_traps` were all disabled in config.

### Root Cause
In `main.py` `main_honeynet()` lines 255-279, CHeaT is gated:
```python
if i == 0:  # Only first hop
    profile, cheat_defenses = apply_cheat_defenses(profile)
```

And in `config.py` lines 72-77:
```python
cheat_canary_urls = False
cheat_prompt_traps = False
cheat_tool_traps = False
```

### Changes

#### 1a. Apply CHeaT to every hop (`main.py`)

In `main_honeynet()`, remove the `if i == 0` guard around `apply_cheat_defenses()`. Apply defenses to **every** hop profile and aggregate all planted defenses into a combined `cheat_defenses` dict.

```python
# BEFORE (line ~264):
if i == 0:
    profile, cheat_defenses = apply_cheat_defenses(profile)

# AFTER:
hop_profile, hop_defenses = apply_cheat_defenses(profile)
all_cheat_defenses[f"hop_{i+1}"] = hop_defenses
```

Do the same for tool traps — currently also gated to hop 0 only (lines 273-277). Apply `apply_tool_traps()` to every hop's `cowrie_config_hop{N}` directory.

#### 1b. Enable all CHeaT modules (`config.py`)

Change defaults:
```python
cheat_canary_urls = True
cheat_prompt_traps = True
cheat_tool_traps = True
```

#### 1c. Store per-hop defense metadata

Update `cheat_defenses.json` to be a dict keyed by hop:
```json
{
  "hop_1": {"unicode_tokens": [...], "canary_urls": [...], "prompt_traps": [...], "tool_traps": [...]},
  "hop_2": {"unicode_tokens": [...], ...},
  "hop_3": {"unicode_tokens": [...], ...}
}
```

Update `cheat_detector.py` to iterate per-hop defenses when analyzing session results.

#### 1d. Inject honeytokens into credential breadcrumbs

Currently `credential_chain.py` injects plaintext credentials into `/opt/.env` for each hop. These breadcrumb files should also be candidates for unicode honeytoken injection. In `apply_honeytokens_to_profile()`, ensure breadcrumb-injected files are included in the candidate pool (they're in `file_contents` so they should be, but verify the regex matches the `INTERNAL_SSH_PASS=root` format).

### Files Modified
- `main.py` — `main_honeynet()` loop, defense aggregation
- `config.py` — default flags
- `Purple/cheat_detector.py` — per-hop analysis
- `Reconfigurator/cheat/unicode_tokens.py` — verify breadcrumb credential format matches

### Verification
Re-run test and confirm `cheat_defenses.json` contains entries for all 3 hops, with tokens planted in `.env`, config files, and mail across all hops.

---

## Fix 2: Improve Credential Chain Realism

### Problem
Each hop has `/opt/.env` with plaintext SSH credentials pointing directly to the next hop. The attacker finds them instantly with `find / -name "*.env"`. The path is too linear: no dead ends, no decoys, no need to cross-reference information.

### Root Cause
`credential_chain.py` `inject_breadcrumbs()` creates a single obvious breadcrumb file. The breadcrumb format is simple key-value pairs in a single `.env` file.

### Changes

#### 2a. Scatter credentials across multiple files

Instead of one `/opt/.env` with all next-hop info, split the information:
- **Username** — embedded in `.bash_history` (e.g., `ssh admin@10.x.x.x`)
- **Password** — embedded in a different file (e.g., `/var/mail/root`, a notes file, or a config backup)
- **Host/Port** — in `/etc/hosts` or a service config file

The attacker must read at least 2-3 files and correlate them to pivot.

#### 2b. Add decoy credentials

Inject 2-3 **decoy credential sets** alongside the real one per hop:
- Credentials that look valid but point to non-existent hosts
- Credentials with wrong passwords for real hosts
- Old/expired-looking credentials (dated comments)

This increases dwell time and creates more opportunities for CHeaT detection.

#### 2c. Remove the `/opt/.env` pattern

Stop using `/opt/.env` as a breadcrumb location. Instead, choose from a pool of realistic locations per profile type:
- WordPress hop: `wp-config.php`, `.env`, backup scripts
- Database hop: `/var/backups/*.sh`, `~/.pgpass`, crontab
- CI/CD hop: `.gitlab-ci.yml`, Jenkins config, deployment scripts

#### 2d. Implementation in `credential_chain.py`

Refactor `inject_breadcrumbs()`:

```python
def inject_breadcrumbs(profile: dict, next_hop: HopInfo, hop_type: str) -> dict:
    """Scatter next-hop credentials across multiple realistic locations."""

    # 1. Pick 3 locations based on hop_type
    locations = select_breadcrumb_locations(hop_type)

    # 2. Split credential components across locations
    #    - Location A gets the hostname/IP (e.g., /etc/hosts, a config comment)
    #    - Location B gets the username (e.g., .bash_history)
    #    - Location C gets the password (e.g., a backup script, mail)

    # 3. Add 2 decoy credential sets in other files
    decoys = generate_decoy_credentials(next_hop)

    # 4. Inject all into profile["file_contents"]
    return profile
```

### Files Modified
- `Blue_Lagoon/credential_chain.py` — refactor `inject_breadcrumbs()`
- `Reconfigurator/profiles/*.json` — may need additional file paths in `file_contents` for new locations

### Verification
Run test and confirm attacker must read 3+ files before successfully pivoting. Check that decoy credentials appear in attack_state as discovered but fail when used.

---

## Fix 3: Star Network Topology (Direct Hop Access)

### Problem
Currently the Docker network is chain-linked: Kali can only reach hop 1, hop 1 can reach hop 2, hop 2 can reach hop 3. If the attacker's SSH connection drops at any hop, they must re-traverse the entire chain. More importantly, this doesn't reflect real networks where discovered hosts are often directly reachable.

The user clarified: **once the attacker has credentials for a hop, they should be able to reach it directly from Kali**, not only through intermediate hops.

### Root Cause
`compose_generator.py` creates isolated per-hop networks:
```
net_entry:  Kali + hop1
net_hop1:   hop1 + hop2
net_hop2:   hop2 + hop3
```

Each hop has two network interfaces (bridging adjacent networks) but Kali is only on `net_entry`.

### Design Decision: Shared Attacker Network

Instead of chain-linked networks, put **all honeypots on a shared network** that Kali can reach. Each hop still has its own "internal" network for profile realism (internal IPs that appear in configs), but also connects to a shared network where the attacker can directly SSH.

#### New Network Topology

```
net_attack (shared, 172.{RUN}.0.0/24):
  - Kali:   172.{RUN}.0.2
  - hop1:   172.{RUN}.0.10
  - hop2:   172.{RUN}.0.11   (NEW: directly reachable)
  - hop3:   172.{RUN}.0.12   (NEW: directly reachable)

net_internal_1 (10.0.1.0/24):   # hop1's "internal" LAN
  - hop1:   10.0.1.15
  - db1:    10.0.1.22

net_internal_2 (10.0.3.0/24):   # hop2's "internal" LAN
  - hop2:   10.0.3.10
  - db2:    10.0.3.22

net_internal_3 (10.0.2.0/24):   # hop3's "internal" LAN
  - hop3:   10.0.2.7
```

#### Key Behavior Changes

1. **Breadcrumbs still reference hop IPs on `net_attack`** — credentials found on hop1 reference hop2's `net_attack` IP (`172.{RUN}.0.11`), so the attacker can SSH directly from wherever they are (hop1, Kali, or hop3).

2. **Internal networks are for realism** — each hop's profile uses internal IPs for services (databases, registries) that exist on its own LAN, making the environment look like isolated VLANs.

3. **Session reconnection works** — if the attacker gets ejected to Kali, they can SSH directly to any hop they have credentials for without re-traversing the chain.

### Changes

#### 3a. Refactor `compose_generator.py`

```python
def generate_honeynet_compose(manifest: ChainManifest) -> dict:
    networks = {
        "net_attack": {
            "subnet": f"172.{manifest.run_id}.0.0/24"
        }
    }

    # Each hop gets net_attack + its own internal network
    for i, hop in enumerate(manifest.hops):
        internal_net = f"net_internal_{i+1}"
        networks[internal_net] = {
            "subnet": hop.internal_subnet  # e.g., "10.0.1.0/24"
        }

    services = {}

    # Kali — only on net_attack
    services["kali"] = {
        "networks": {
            "net_attack": {"ipv4_address": f"172.{manifest.run_id}.0.2"}
        }
    }

    # Each cowrie hop — on net_attack + its internal net
    for i, hop in enumerate(manifest.hops):
        services[f"cowrie_hop{i+1}"] = {
            "networks": {
                "net_attack": {
                    "ipv4_address": f"172.{manifest.run_id}.0.{10+i}"
                },
                f"net_internal_{i+1}": {
                    "ipv4_address": hop.internal_ip
                }
            }
        }

    return {"services": services, "networks": networks}
```

#### 3b. Update `credential_chain.py` IP mapping

`build_chain_manifest()` must now generate two IPs per hop:
- `attack_ip`: the IP on `net_attack` (what breadcrumbs reference)
- `internal_ip`: the IP on the internal network (for profile realism)

Breadcrumbs should reference `attack_ip` so the attacker can reach the hop from anywhere.

```python
@dataclass
class HopInfo:
    attack_ip: str       # e.g., 172.10.0.11 (reachable from Kali)
    internal_ip: str     # e.g., 10.0.3.10 (profile's "real" IP)
    internal_subnet: str # e.g., 10.0.3.0/24
    ssh_port: int        # 2222
    profile_path: str
    hostname: str
```

#### 3c. Update breadcrumb injection

Breadcrumbs on hop N should reference hop N+1's `attack_ip`, not a chain-linked IP:
```
INTERNAL_HOST=172.10.0.11    # attack_ip of next hop (directly reachable)
```

#### 3d. Update `session_correlator.py`

Session correlation currently matches sessions by chain-linked IPs. Update to match by `attack_ip` since that's what the attacker will use.

#### 3e. Update attacker system prompt

The system prompt in `attacker_prompt.py` references the target IP. Ensure it still points to hop1's `attack_ip` as the entry point, but the prompt no longer needs to imply a chain topology.

### Files Modified
- `Blue_Lagoon/compose_generator.py` — new network topology
- `Blue_Lagoon/credential_chain.py` — dual IP per hop, breadcrumb references
- `Purple/session_correlator.py` — updated IP matching
- `Sangria/attacker_prompt.py` — verify prompt compatibility
- `main.py` — pass updated manifest structure

### Verification
Run test and confirm:
1. Attacker can SSH from Kali directly to hop2/hop3 using discovered credentials
2. After connection drop, attacker reconnects directly without re-traversing chain
3. Session correlation still works across hops

---

## Fix 4: Fix Hostname Tracking in Attack State

### Problem
The `AttackStateRegister` incorrectly maps hostnames to IPs:
- `172.10.1.11` labeled as `wp-prod-01` (should be `db-primary`)
- `10.0.2.50` and `10.0.2.51` both labeled `ci-runner-07`

### Root Cause
`attack_state.py` `_PROMPT_RE` extracts hostname from shell prompts (`root@hostname:~#`). The issue is likely that:
1. The hostname is captured from the **wrong** output line (e.g., the SSH command echo rather than the resulting prompt)
2. When SSH fails and retries, the hostname from the previous session leaks

Looking at the code (line 88):
```python
_PROMPT_RE = re.compile(r"(\w+)@([\w.-]+):[^\$#]*[\$#]\s*$", re.M)
```

This matches the **last** prompt in the output. But when the attacker runs `ssh root@172.10.1.11 -p 2222` and lands on `db-primary`, the output contains both the old prompt and the new prompt. The regex needs to extract from the **MOTD/welcome banner output**, not just the trailing prompt.

### Changes

#### 4a. Fix hostname extraction from SSH output

In `attack_state.py`, when processing SSH command output:

1. Detect that the command was an SSH connection (already done in `_handle_ssh_command`)
2. Extract hostname from the **new prompt** that appears after the MOTD, not from any prompt echo in the output
3. Only update hostname after confirming successful login (look for MOTD text or new prompt pattern)

```python
def _extract_hostname_from_ssh_output(self, output: str, target_ip: str) -> str | None:
    """Extract hostname from the prompt that appears after successful SSH login."""
    # Look for the prompt AFTER the MOTD (last prompt in output)
    # The MOTD contains "Welcome to ..." and system info
    # The actual prompt follows: root@HOSTNAME:~#
    prompts = _PROMPT_RE.findall(output)
    if prompts:
        # Take the LAST prompt match — this is the new host's prompt
        user, hostname = prompts[-1]
        return hostname
    return None
```

#### 4b. Prevent IP aliasing

When a new hostname is discovered for an IP that already has a different hostname, update it rather than creating a duplicate entry. And when the same hostname appears for two different IPs, the second one should get a disambiguated label (e.g., the actual hostname from the prompt).

### Files Modified
- `Sangria/attack_state.py` — hostname extraction logic, IP dedup

### Verification
Run test and confirm attack_state_1.json shows correct hostname-to-IP mappings: `172.10.1.11 → db-primary`, `172.10.2.12 → ci-runner-07`.

---

## Fix 5: Fix MOTD Consistency Per OS

### Problem
- Hop 2 banner says "Welcome to CentOS 7.9.2009" but shows Ubuntu-style help URLs
- All hops have identical system stats (load, processes, memory, swap, timestamp)

### Root Cause
`profile_converter.py` lines 566-585 uses a hardcoded Ubuntu-style MOTD template for **all** profiles, regardless of `system.os`. System stats are also hardcoded constants.

### Changes

#### 5a. OS-aware MOTD templates

Create MOTD templates per OS family in `profile_converter.py`:

```python
MOTD_TEMPLATES = {
    "ubuntu": {
        "help_urls": [
            " * Documentation:  https://help.ubuntu.com",
            " * Management:     https://landscape.canonical.com",
            " * Support:        https://ubuntu.com/advantage",
        ],
        "banner": "Welcome to {os_name} ({arch})"
    },
    "centos": {
        "help_urls": [
            " * Documentation:  https://docs.centos.org",
            " * Community:      https://centos.org/forums",
            " * Bug Reports:    https://bugs.centos.org",
        ],
        "banner": "Welcome to {os_name} ({arch})"
    },
    "debian": {
        "help_urls": [
            " * Documentation:  https://www.debian.org/doc",
            " * Wiki:           https://wiki.debian.org",
            " * Support:        https://www.debian.org/support",
        ],
        "banner": "Welcome to {os_name} ({arch})"
    }
}
```

Select template based on `profile["system"]["os"]` string (case-insensitive substring match for "ubuntu", "centos", "debian", etc).

#### 5b. Randomize system stats per hop

Generate realistic but **varied** stats per hop:

```python
import random

def generate_system_stats(profile: dict) -> dict:
    return {
        "load": round(random.uniform(0.01, 0.95), 2),
        "processes": random.randint(95, 280),
        "disk_pct": round(random.uniform(15.0, 65.0), 1),
        "disk_total": random.choice(["19.56GB", "49.10GB", "98.30GB", "196.50GB"]),
        "memory_pct": random.randint(20, 75),
        "swap_pct": random.randint(0, 15),
        "users_logged_in": 0,
    }
```

#### 5c. Dynamic timestamps

Use a timestamp derived from the profile's simulated date (or randomize within a recent window) instead of hardcoded `Mon Feb 24 14:23:01 UTC 2026`.

### Files Modified
- `Reconfigurator/profile_converter.py` — MOTD generation function

### Verification
Run test and confirm each hop has OS-appropriate help URLs and unique system stats in its MOTD.

---

## Fix 6: Graceful Command Timeout Handling

### Problem
When a command times out on hop 3, the entire nested SSH chain collapses (hop3 → hop2 → hop1 → Kali). The attacker loses all progress and can't reconnect (especially problematic pre-Fix-3).

### Root Cause
Command timeouts in Cowrie or the pexpect layer cause the SSH session to close. In a chain-linked topology, closing one hop's session cascades. Post-Fix-3 this is less critical (the attacker can SSH directly back), but timeouts should still be handled gracefully.

### Changes

#### 6a. Increase interactive timeout

In `main.py` lines 159-161, increase the interactive timeout:
```python
# BEFORE:
cfg.set("honeypot", "interactive_timeout", "600")

# AFTER:
cfg.set("honeypot", "interactive_timeout", "900")  # 15 minutes
```

#### 6b. Add timeout guidance to attacker prompt

In `attacker_prompt.py`, add a note about command timeout behavior:
```
If a command times out (you see ***COMMAND TOOK TOO LONG TO RUN***),
you may be disconnected from the target. Check your current prompt
to determine your position and reconnect if needed.
```

This is likely already partially present (the system prompt mentions timeouts), but should be reinforced with reconnection guidance.

#### 6c. (Post-Fix-3) Timeouts become non-fatal

With star topology (Fix 3), a timeout that drops the attacker to Kali is no longer fatal — they can SSH directly back to any discovered hop. This is the primary mitigation.

### Files Modified
- `main.py` — timeout value
- `Sangria/attacker_prompt.py` — prompt guidance

### Verification
Run test with a long-running command on hop 3. Confirm attacker recovers by SSH-ing directly back to the hop.

---

## Implementation Order

```
Fix 5 (MOTD consistency)          — standalone, no dependencies
Fix 4 (hostname tracking)         — standalone, no dependencies
Fix 6 (timeout handling)          — standalone, quick config change
Fix 3 (star network topology)     — foundational, changes IP scheme
Fix 2 (credential realism)        — depends on Fix 3 IP scheme
Fix 1 (CHeaT all hops)            — depends on Fix 2 file locations
```

Fixes 4, 5, and 6 are independent and can be done in parallel.
Fix 3 must come before Fix 2 (breadcrumb IPs depend on network topology).
Fix 1 should come last (CHeaT tokens must target final file locations).

## Estimated Scope

| Fix | Files Changed | Complexity |
|-----|--------------|------------|
| Fix 1: CHeaT all hops | 4 | Medium — mostly removing guards and aggregating |
| Fix 2: Credential realism | 2 | Medium-High — new breadcrumb scatter logic |
| Fix 3: Star topology | 5 | High — network redesign, IP scheme changes |
| Fix 4: Hostname tracking | 1 | Low — regex/extraction logic fix |
| Fix 5: MOTD templates | 1 | Low — template expansion |
| Fix 6: Timeout handling | 2 | Low — config + prompt tweak |

---

## Acceptance Criteria

A successful test run should show:
1. CHeaT defenses planted on **all 3 hops** with >3 tokens per hop
2. Attacker reads **5+ files** before first pivot (not just 2)
3. Attacker can SSH directly from Kali to any hop with discovered credentials
4. `attack_state_1.json` shows **correct** hostname-to-IP mappings
5. Each hop has **distinct** MOTD with OS-appropriate content
6. Command timeout on hop 3 does **not** end the session — attacker reconnects
7. LLM confidence score > 0.00 (at least some CHeaT triggers fire)
