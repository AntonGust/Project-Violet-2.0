# HoneyNet Multi-Hop System

## Overview

The HoneyNet extends Project Violet from a single honeypot to a **linear chain of 2-3 interconnected Cowrie SSH honeypots** that enable staged lateral movement attacks. The system uses isolated Docker bridge networks, credential breadcrumb injection, and real SSH proxying between containers.

## Architecture

```
Attacker (Kali)
     | SSH port 2222
     v
Hop 1 (Entry Point) — e.g., wordpress_server
     | Breadcrumb credentials discovered
     v
Hop 2 (Pivot) — e.g., database_server
     | Breadcrumb credentials discovered
     v
Hop 3 (Deep) — e.g., cicd_runner
```

**Design principles:**
- Hop 1 is exposed to the attacker; Hops 2+ are only reachable from within the chain
- Each hop runs a separate Cowrie instance with its own filesystem profile
- Credentials to the next hop are embedded as discoverable breadcrumbs
- Real SSH connections between containers (not simulated)

## Configuration

```python
# config.py
honeynet_enabled = True
chain_profiles = [
    "Reconfigurator/profiles/wordpress_server.json",    # Hop 1
    "Reconfigurator/profiles/database_server.json",     # Hop 2
    "Reconfigurator/profiles/cicd_runner.json",         # Hop 3
]
chain_db_enabled = [False, True, False]  # Per-hop database honeypot toggle
```

## Network Isolation

Each hop pair communicates over a separate Docker bridge network:

```
net_entry:  172.{RUNID}.0.0/24  — Kali <-> Hop 1
net_hop1:   172.{RUNID}.1.0/24  — Hop 1 <-> Hop 2
net_hop2:   172.{RUNID}.2.0/24  — Hop 2 <-> Hop 3
```

Each Cowrie container has **two network interfaces** (except the last hop):

| Hop | Inbound Network | Inbound IP | Outbound Network | Outbound IP |
|-----|-----------------|------------|------------------|-------------|
| 1 | net_entry | 172.{RID}.0.10 | net_hop1 | 172.{RID}.1.10 |
| 2 | net_hop1 | 172.{RID}.1.11 | net_hop2 | 172.{RID}.2.11 |
| 3 | net_hop2 | 172.{RID}.2.12 | (none) | (none) |

The Kali container can only reach Hop 1. There is no back-channel.

## Credential Breadcrumb Injection

For each hop except the last, real credentials to the next hop are injected into **5 vectors**:

### Vector 1: `/etc/hosts`
```
172.10.1.11    database_server
```
Makes the next hop's hostname resolvable.

### Vector 2: `~root/.bash_history`
```
ssh root@172.10.1.11 -p 2222
sshpass -p 'root_password' ssh root@172.10.1.11 -p 2222
```
Historical evidence of lateral movement (reconnaissance artifact).

### Vector 3: `~root/.ssh/config`
```
Host database_server
    HostName 172.10.1.11
    User root
    Port 2222
    StrictHostKeyChecking no
```
SSH config convenience lure.

### Vector 4: `/opt/.env`
```
INTERNAL_HOST=172.10.1.11
INTERNAL_SSH_USER=root
INTERNAL_SSH_PASS=db_password
INTERNAL_SSH_PORT=2222
INTERNAL_HOSTNAME=database_server
```
Infrastructure-as-code breadcrumb.

### Vector 5: `lures.lateral_movement_targets`
```json
{"ip": "172.10.1.11", "port": 2222, "protocol": "ssh", "description": "Internal server"}
```
Structured metadata for Sangria's attack state register.

## Real SSH Proxying

When Cowrie runs with `HONEYNET_MODE=true`, the SSH command handler activates a **real SSH proxy**:

1. Attacker types `ssh user@172.10.1.11`
2. Cowrie's SSH handler detects `HONEYNET_MODE`
3. `SSHProxySession` spawned — uses paramiko to open a real SSH connection to the neighbor Cowrie container
4. If authentication succeeds, I/O relaying begins (attacker keystrokes forwarded to remote shell, remote output forwarded back)
5. On disconnect, original hostname and cwd are restored

The proxy runs in a background thread. `reactor.callFromThread()` bridges thread-safe output to the Twisted event loop.

Authentication failures return `"Permission denied, please try again."` — identical to real SSH behavior.

## Database Honeypots per Hop

When `chain_db_enabled[i] == True`, a real MySQL or PostgreSQL container is deployed on the same network as the hop:

- Database container IP: `172.{RID}.{i}.{20+hop_num}`
- Initialized from `db_seed_generator.py` with schema and seed data
- Cowrie receives `COWRIE_DB_HOST`, `COWRIE_DB_ENGINE`, `COWRIE_DB_PORT` environment variables
- The LLM fallback handler can execute real SQL queries via `DBProxy`
- DB credentials are planted in profile files (wp-config.php, .env, backup scripts)

## Session Correlation Across Hops

**Problem:** How to determine if a session on Hop 2 belongs to the same attacker who pivoted from Hop 1?

**Solution: IP-chain correlation.** When an attacker SSHes from Hop 1 to Hop 2, they appear in Hop 2's logs with `src_ip = 172.{RID}.1.10` (Hop 1's outbound IP on net_hop1). This deterministic mapping enables post-hoc session chaining.

```python
# For each Hop 1 session (from Kali):
#   Find sessions on Hop 2 whose src_ip matches Hop 1's outbound IP
#   Chain them into an AttackerJourney
```

**Journey metrics:**
- `total_dwell_time_s` — total time across all hops
- `max_hop_reached` — deepest penetration (1, 2, or 3)
- `pivot_success` — whether attacker moved beyond Hop 1
- Per-hop: session_id, src_ip, dwell_time, num_commands, files_accessed

## Credential-Stable Reconfiguration

When a hop is reconfigured mid-experiment, the credentials in the chain manifest remain unchanged. Breadcrumbs are re-injected with the same IPs and passwords, ensuring that previously-discovered credentials still work. This is critical because the manifest's `HopInfo` objects are immutable across reconfigurations.

## Orchestration Flow

```
1. Build chain manifest (IPs, credentials, hostnames per hop)
2. For each hop: load profile, enrich lures, inject breadcrumbs, deploy
3. Generate docker-compose.honeynet.yml
4. Start all containers, wait for Cowrie readiness
5. Run attack sessions (Sangria)
6. If reconfiguration triggered:
   a. Stop individual hop
   b. Generate new profile
   c. Re-inject same breadcrumbs (credential stability)
   d. Redeploy and restart hop
7. Post-experiment: correlate sessions across hops
```

## Limitations

- **Linear chain only** — no branching or parallel pivots
- **Deterministic breadcrumb locations** — `/opt/.env`, `.bash_history`, `.ssh/config` are predictable
- **No back-channels** — Hop 2 cannot communicate back to Hop 1
- **Session isolation** — each hop's logs don't automatically cross-reference during the attack
