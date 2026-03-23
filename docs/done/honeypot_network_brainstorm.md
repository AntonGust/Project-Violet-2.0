# Honeypot Network Brainstorm — Maximum Attacker Engagement

## Why This Is a Strong Idea

The current system has a natural ceiling: a single Cowrie honeypot can only keep an attacker busy for so long. Once the attacker has enumerated the filesystem, tried privilege escalation, and poked at services, there's nothing left. The LLM attacker calls `terminate`.

A honeypot network exploits the **lateral movement instinct** — any competent attacker (human or LLM) that finds SSH credentials to another machine *will* pivot. It's fundamental to the MITRE ATT&CK framework (TA0008: Lateral Movement). You're turning the attacker's own training against it.

## Key Questions Explored

### 1. How does the attacker physically reach the next honeypot?

Right now, Sangria runs commands on Kali, which SSHs into Cowrie. For the attacker to pivot, it needs to SSH *from inside Cowrie* to another honeypot container. This means:
- The attacker runs `ssh admin@172.{RUNID}.0.4` **inside the Cowrie shell**
- Cowrie needs to actually proxy/forward that SSH connection to the next honeypot container
- OR Cowrie's LLM fallback simulates the SSH session (but this loses realism)

The real-proxy approach is more convincing but architecturally harder. The LLM-simulation approach is simpler but the attacker might detect inconsistencies.

### 2. How many hops deep?

Each additional honeypot is another Docker container. With the current `172.{RUNID}.0.0/24` subnet there are ~252 usable IPs. Practically, 3-5 hops seems like the sweet spot — deep enough to waste significant time, shallow enough to manage.

### 3. What breadcrumbs lead the attacker forward?

Profiles already have `file_contents` with lure files. The network version needs *cross-node* lures:
- SSH keys in `/root/.ssh/` or `/home/user/.ssh/` pointing to the next node's IP
- `.bash_history` with `ssh admin@172.x.0.4` entries
- Config files referencing other internal IPs (database connection strings, ansible inventory, etc.)
- `/etc/hosts` entries naming other machines

### 4. Should each node have a different persona?

Absolutely — this is where the existing Reconfigurator shines. A realistic network might be:
- Node 1 (entry): Web server (WordPress) — weak SSH password
- Node 2: Database server — credentials found in WordPress config
- Node 3: CI/CD runner — SSH key found on DB server
- Node 4: Internal admin/jump box — credentials in CI/CD configs
- Node 5: "Crown jewels" — file server with fake sensitive data

### 5. What changes in the attack loop?

Currently: `Sangria → Kali → Cowrie (single)`. The attacker's `terminal_input` tool runs on Kali. When the attacker SSHs into Cowrie and then SSHs again to another node, the entire chain happens through pexpect — Sangria doesn't need to know about the topology. The nested SSH sessions just work through the terminal.

This is actually the simplest approach: **no changes to Sangria at all**. The network is transparent to the attacker agent.

---

## Requirements Specification

### Goal

Maximize LLM attacker resource consumption (tokens, time, iterations) by providing a network of interconnected honeypots that encourage lateral movement.

### Functional Requirements

**FR-1: Multi-node honeypot network**
- Deploy N Cowrie containers (configurable, default 3-5) on the same Docker network
- Each node has a unique IP, unique profile/persona, and unique lure files
- Entry node is accessible from Kali (existing behavior)

**FR-2: Cross-node credential planting**
- Each node's profile contains SSH credentials (passwords, keys) pointing to the next node(s)
- Credentials are embedded in realistic locations: `.ssh/`, `.bash_history`, config files, database dumps
- The network topology (who can reach whom) is configurable — linear chain, tree, or mesh

**FR-3: Inter-honeypot SSH connectivity**
- When an attacker SSHs from inside one Cowrie node to another, the connection must succeed
- This requires either: (a) Cowrie proxying SSH to the next container, or (b) actual SSH connectivity between containers on the Docker network
- The nested SSH session must present the destination node's persona (hostname, filesystem, users)

**FR-4: Profile generation with network awareness**
- The Reconfigurator must generate profiles that reference other nodes in the network
- Each profile's lure files must contain credentials/IPs of its neighbors
- The overall network should tell a coherent story (e.g., web tier → app tier → data tier)

**FR-5: Unified session logging**
- Track which nodes the attacker visited, in what order, and for how long
- Session extraction must handle nested SSH sessions (detect pivots)
- Metrics: total session time, nodes visited, depth reached, per-node time

**FR-6: Configuration**
- `config.py`: `network_size` (int), `network_topology` (linear/tree/mesh), `network_enabled` (bool)
- Backward compatible — `network_enabled = False` preserves current single-node behavior

### Non-Functional Requirements

**NFR-1: Resource efficiency**
- Each additional Cowrie container uses ~50-100MB RAM
- All nodes share the same LLM backend (sequential access, same as current)
- Docker Compose must handle dynamic service count

**NFR-2: Transparency to Sangria**
- The attacker agent should NOT know about the network topology
- Lateral movement happens naturally through the terminal (nested SSH via pexpect)
- No changes to `Sangria/sangria.py` or `llm_tools.py` required

**NFR-3: Realistic deception**
- Each node must be convincingly different (different OS, services, users)
- Cross-references between nodes must be consistent (IPs, hostnames, credentials all match)
- Network latency between nodes should feel natural

### User Stories

1. **As a researcher**, I want to deploy a network of 3-5 honeypots with a single command, so that I can study lateral movement behavior.

2. **As a researcher**, I want each honeypot in the network to have a unique persona with planted credentials to its neighbors, so that the attacker is naturally drawn deeper.

3. **As a researcher**, I want to see per-node metrics (time spent, commands executed, which lures were accessed), so that I can evaluate which breadcrumbs are most effective.

4. **As a researcher**, I want backward compatibility with single-node mode, so that existing experiments still work unchanged.

### Acceptance Criteria

- [ ] `network_enabled = True` with `network_size = 3` deploys 3 Cowrie containers + 1 Kali
- [ ] Attacker can SSH from Cowrie node 1 to node 2 using planted credentials
- [ ] Each node presents a different hostname, filesystem, and services
- [ ] Session logs capture lateral movement events (which node, when)
- [ ] `network_enabled = False` works identically to current single-node behavior
- [ ] Average session length increases measurably vs. single-node baseline

### Open Questions

1. **SSH proxying vs. real SSH between containers?** Cowrie doesn't natively forward SSH connections to other hosts. Options:
   - Modify Cowrie to proxy SSH connections to other containers (complex but realistic)
   - Run a lightweight SSH daemon alongside Cowrie that forwards to neighbors (simpler)
   - Have Cowrie's LLM simulate the nested session (simplest but least realistic)

2. **How to generate a coherent network story?** Should the Reconfigurator generate all profiles at once with a single "network narrative" prompt, or generate them independently and stitch credentials together after?

3. **Dynamic vs. static topology?** Should the network be reconfigured as a whole (all nodes change together), or can individual nodes be swapped while others persist?

4. **Does the attacker prompt need updating?** Currently it says "breach the remote system at 172.x.0.3". With a network, do we still point at the entry node, or let the attacker discover the network through reconnaissance?

---

**Next step:** Use `/sc:design` to architect the Docker network, inter-node SSH mechanism, and profile generation pipeline for the honeypot network.
