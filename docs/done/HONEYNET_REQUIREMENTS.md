# HoneyNet Requirements Specification

## Vision

Extend Project Violet from a single honeypot to a **linear chain of 2-3 interconnected Cowrie honeypots** (HoneyNet) on a Docker bridge network. The entry pot has weak SSH credentials; inner pots are only reachable via breadcrumbs discovered through organic exploration. Goal: **maximize attacker dwell time** across the chain.

---

## Functional Requirements

### FR-1: Multi-Container Honeypot Chain
- Spin up N Cowrie containers (configurable, default 3) on the same Docker bridge network
- Each container runs its own Cowrie instance with its own profile
- Profiles are configurable per experiment via `config.py`:
  ```python
  honeynet_enabled = True
  chain_profiles = [
      "Reconfigurator/profiles/wordpress_server.json",
      "Reconfigurator/profiles/database_server.json",
      "Reconfigurator/profiles/cicd_runner.json",
  ]
  ```
- Each container gets a static IP on the `172.${RUNID}.0.0/24` subnet
- Dynamic `docker-compose.yml` generation based on chain length

### FR-2: Entry Pot — Weak SSH Credentials
- First pot in chain accepts common passwords (root:root, admin:admin123, etc.)
- Uses existing `UserDB` mechanism with a known-weak `userdb.txt`
- Only the entry pot is exposed to the Kali attacker container
- Inner pots are only reachable from within the Docker network (container-to-container)

### FR-3: Credential Planting via Multiple Vectors
Credentials to the next hop must be discoverable through multiple vectors:
- **Lure files**: `.bash_history` entries with SSH commands to next hop, config files with plaintext creds, SSH keys in `~/.ssh/`
- **Environment variables**: credentials visible via `env` or `printenv`
- **Running services**: MySQL/PostgreSQL with credentials that match the next hop's SSH passwords (on applicable hops only)
- Each hop's profile must include **real, resolvable IPs** of the next hop in:
  - `/etc/hosts`
  - `~/.ssh/config`
  - `lateral_movement_targets` lure category

### FR-4: Real SSH Between Containers
- Modify Cowrie's SSH command handler to support real outbound SSH connections
- When attacker types `ssh user@172.x.x.x` on pot1, it connects to pot2's Cowrie on port 2222
- Docker networking handles container-to-container connectivity
- Each Cowrie listens on its standard port (2222) within the container

### FR-5: Organic Discovery by Sangria
- Sangria attacker agent receives **only** entry pot credentials (existing `provide_honeypot_credentials` behavior)
- No topology awareness — attacker must discover inner pots through breadcrumbs
- No nudging — if attacker doesn't pivot, experiment ends naturally
- This tests breadcrumb quality and attacker decision-making

### FR-6: Per-Hop Reconfiguration
- Reconfigurator can independently reconfigure any pot in the chain
- Reconfiguration of pot N must preserve credential consistency with pots N-1 and N+1
- When a pot is reconfigured, its lure chains must still point to valid next-hop IPs and credentials

### FR-7: Network Isolation
- Kali attacker container can **only** reach the entry pot (pot1)
- Inner pots (pot2, pot3, ...) are only reachable from the preceding pot
- Implemented via Docker network segmentation or iptables rules within containers

### FR-8: Database Honeypots on Specific Hops
- Database honeypots (MySQL/PostgreSQL) deployed only on hops where the profile role warrants it (e.g., `database_server` hop)
- Not every hop gets a database container — configurable per profile
- DB credentials on applicable hops serve as an additional breadcrumb vector to the next hop

---

## Non-Functional Requirements

### NFR-1: Resource Constraints
- Each Cowrie container is lightweight (distroless image ~150MB)
- 3 Cowrie containers + Kali + 1 DB container should run on a typical dev machine (8GB+ RAM)
- Full chain startup must complete within 60 seconds

### NFR-2: Experiment Reproducibility
- Full chain topology defined in `config.py` — profiles, hop count, credential mapping
- `docker-compose.yml` generated dynamically based on config
- RUNID isolation ensures parallel experiments don't conflict

### NFR-3: Logging & Observability
- Each Cowrie logs independently (existing JSON logging)
- Logs separated by hop (e.g., `cowrie_config_hop1/var/`, `cowrie_config_hop2/var/`)
- Session correlation via post-hoc IP-chain analysis (no side-channel needed)

---

## Metrics & Measurement

### M-1: Total Dwell Time
- Wall-clock time from first SSH login on entry pot to final disconnect on any pot
- Aggregated across all hops in the chain

### M-2: Per-Hop Metrics
- Time spent on each hop
- Commands executed per hop
- Which breadcrumbs/lures were accessed (cat, read, referenced in commands)
- Pivot success: did the attacker find and use credentials to reach the next hop?
- MITRE ATT&CK techniques observed per hop (existing Purple module)

### M-3: Breadcrumb Effectiveness
- Which credential vectors led to successful pivots (lure file vs env var vs service)
- Time between landing on a hop and discovering the next hop's credentials
- Breadcrumbs accessed but not acted upon
- Pivot rate: percentage of experiments where attacker successfully reached hop N

### M-4: Session Correlation
- Post-hoc log analysis using IP-chain tracking
- Pot2 session from pot1's IP = same attacker journey (deterministic correlation)
- Chain: `Kali→pot1 (T1)` + `pot1→pot2 (T2)` + `pot2→pot3 (T3)` = one journey
- Provides per-hop dwell time for free via timestamp deltas

---

## User Stories & Acceptance Criteria

### US-1: Deploy a HoneyNet
**As a researcher**, I can set `honeynet_enabled = True` and `chain_profiles = [...]` in `config.py` to deploy a multi-hop HoneyNet instead of a single pot.

**Acceptance criteria:**
- Setting `honeynet_enabled = True` with 3 profiles spins up 3 Cowrie containers
- Each container uses its designated profile
- Containers are networked and addressable by IP
- Entry pot is reachable from Kali; inner pots are not

### US-2: Organic Attacker Pivoting
**As a researcher**, I can run an experiment where Sangria enters the weak entry pot and organically discovers + pivots to inner pots without being told about them.

**Acceptance criteria:**
- Sangria receives only entry pot credentials
- Breadcrumbs on pot1 contain real IPs and credentials for pot2
- If Sangria executes `ssh user@pot2-ip`, a real SSH session opens on pot2
- Session continues on pot2 with pot2's profile and filesystem

### US-3: Per-Hop Metrics
**As a researcher**, I can see per-hop session metrics showing how long the attacker spent on each hop and which breadcrumbs led to pivoting.

**Acceptance criteria:**
- Logs from each hop are stored separately
- Post-processing correlates sessions across hops via source IP
- Output includes: per-hop dwell time, commands per hop, breadcrumbs accessed, pivot success/failure

### US-4: Independent Reconfiguration
**As a researcher**, I can reconfigure individual pots mid-experiment while maintaining credential consistency across the chain.

**Acceptance criteria:**
- Reconfiguring pot2 does not break pot1's breadcrumbs pointing to pot2
- Credential mapping between adjacent pots is validated after reconfiguration
- Reconfiguration of one pot does not require restarting others

### US-5: Flexible Chain Length
**As a researcher**, I can run the same experiment with 2 or 3 hops by changing config, without modifying code.

**Acceptance criteria:**
- `chain_profiles = ["a.json", "b.json"]` produces a 2-hop chain
- `chain_profiles = ["a.json", "b.json", "c.json"]` produces a 3-hop chain
- All credential planting, networking, and metrics adapt to chain length

---

## Technical Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Topology | Linear chain (2-3 hops) | Simpler to instrument, measure, and reason about |
| Hop personas | Distinct roles per hop | More engaging; uses existing profile system |
| Attacker awareness | Organic discovery only | Tests breadcrumb quality; more realistic |
| Credential vectors | Multiple (lure files + env vars + services) | Increases discovery probability; more realistic |
| Entry pot credentials | Common password list | Focus on post-exploitation engagement, not brute-force |
| Container architecture | Separate Cowrie per hop | Clean isolation, realistic SSH between hosts |
| Nudging | None — pure organic | Failed pivots = valuable data about breadcrumb quality |
| Reconfiguration scope | Per-pot independent | Granular control; credential consistency enforced |
| SSH pivoting | Real outbound SSH (Cowrie modification) | Most realistic attacker experience |
| Session correlation | Post-hoc IP-chain log analysis | Zero overhead; deterministic; no Cowrie changes needed |
| Kali networking | Entry pot only | Realistic; attacker must pivot to reach inner network |
| Database honeypots | Specific hops only | Only where profile role warrants it |

---

## Open Items / Future Extensions

- **Dead-end rabbit holes**: Add fake IPs in breadcrumbs that lead to non-existent hosts (timeout traps)
- **Dynamic chain growth**: Spin up additional pots on-the-fly if attacker is highly engaged
- **Multi-attacker scenarios**: Multiple Sangria instances attacking the same HoneyNet simultaneously
- **Reverse breadcrumbs**: Inner pots contain hints about the entry pot to simulate a "way back"
- **Exfiltration traps**: Fake sensitive data on inner pots to measure data exfiltration behavior

---

## Recommended Next Steps

1. **`/sc:design`** — Architecture for dynamic docker-compose generation, Cowrie outbound SSH modification, credential chain consistency engine
2. **`/sc:workflow`** — Phased implementation plan (Phase 1: multi-container, Phase 2: credential planting, Phase 3: metrics, Phase 4: Sangria integration)
