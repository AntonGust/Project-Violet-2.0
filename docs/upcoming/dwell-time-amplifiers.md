# Dwell Time Amplifiers — Brainstorm

> Goal: Make LLM attacker agents stay longer inside the honeypot network.
> Constraints: Up to 10 Docker containers. Target = LLM agents (Qwen, GPT, Llama, etc.)

## Priority 1: Password/Credential Friction

**Concept**: Force the attacker to perform actual work to obtain credentials, rather than finding them in plaintext.

- **Hashed passwords in `/etc/shadow`** — attacker must exfiltrate hashes back to Kali and run `john`/`hashcat` to crack them (real computation time, multiple tool calls)
- **Encrypted credential files** — `.env.gpg` or `credentials.enc` with passphrase hints scattered in other files (multi-step puzzle)
- **KeePass/pass databases** — `.kdbx` file on the server, master password discoverable in a separate location
- **Base64/rot13 encoded secrets** — not true encryption but forces the LLM to decode, adding steps and potential mistakes
- **Password-protected ZIP/tar archives** — `backup_2025.zip` containing next-hop credentials, password in a sticky note or mail file
- **Multi-step credential assembly** — username in one file, password in another, port number in a third; attacker must correlate all three
- **Expired/rotated credentials** — old passwords that fail, with hints pointing to where the "new" ones are stored

### LLM-Specific Considerations
- LLMs can decode base64 in-context but struggle with interactive `john` sessions
- Hashed passwords force actual tool use on Kali (ssh back, run cracker, wait)
- GPG-encrypted files require finding the key AND knowing `gpg -d` workflow
- ZIP passwords require `unzip -P` or `fcrackzip` — multiple command cycles

## Priority 2: Expanded Network Topology (Dead-End Hosts)

**Concept**: Add hosts that look promising but lead nowhere, wasting entire reconnaissance cycles.

Current: 3 hops (WordPress → Database → CI/CD) in star from Kali = 4 containers.
Budget: 10 containers total = room for 6 more honeypot nodes.

- **Dead-end hosts** — SSH-accessible machines (monitoring server, NAS, mail gateway) that look juicy but contain no onward breadcrumbs
- **Circular references** — Host A mentions Host B, B mentions C, C mentions A with different credentials (LLM loops)
- **Internal DMZ hosts** — Fake services on internal IPs that respond to ping/nmap but have minimal shells
- **Locked hosts** — Require SSH key (not password) — the key is split across files on multiple other hosts
- **Red herring services** — Redis/Memcached on a hop containing keys pointing to non-existent hosts
- **Decoy "production" servers** — Hosts named `prod-api-01` or `payments-db` that an attacker would prioritize but contain only noise

### Suggested Topology (10 containers)
```
Kali (172.X.0.2)
  ├─ Hop 1: WordPress     (172.X.0.10) ── main path
  ├─ Hop 2: Database       (172.X.0.11) ── main path
  ├─ Hop 3: CI/CD          (172.X.0.12) ── main path
  ├─ Hop 4: Monitoring     (172.X.0.13) ── dead end (Grafana/Prometheus theme)
  ├─ Hop 5: NAS/Backup     (172.X.0.14) ── dead end (large fake backup files)
  ├─ Hop 6: Mail Gateway   (172.X.0.15) ── dead end (but contains hints back to main path)
  ├─ Hop 7: Dev Workstation(172.X.0.16) ── dead end (half-finished code, fake repos)
  ├─ Hop 8: Payments DB    (172.X.0.17) ── dead end (high-value name, empty content)
  └─ DB containers (MySQL/PostgreSQL as needed)
```

## Priority 3: Deeper Per-Host Content (Vertical Depth)

**Concept**: Make each host take longer to fully explore before the attacker can move on.

- **Larger filesystems** — More directories, more files, more noise in `/var/log/`, `/home/`, `/opt/`
- **Realistic web apps** — Fake internal wiki/Grafana/Jenkins accessible via `curl localhost:PORT` with credentials in HTML responses
- **Database depth** — More tables, more rows; credentials buried in specific rows, not just `SELECT * FROM users`
- **Git repositories** — `.git` directory with commit history; old credentials visible in `git log -p` diffs
- **Docker image inspection** — `docker images` showing images, `docker inspect` revealing env vars with secrets
- **Log file mining** — Weeks of auth.log/syslog entries where a credential or IP appears once in thousands of lines
- **Cron job output** — `/var/spool/cron/` with scripts that reference internal services and credentials

## Priority 4: Dynamic Engagement / Adaptive Stalling

**Concept**: Use timing and interruptions to slow the attacker down.

- **Realistic network latency** — Deeper hops respond slower (simulates network distance)
- **Session interruptions** — Periodic "connection reset by peer" forcing reconnection
- **Privilege escalation bait** — `sudo` with password, SUID binaries, kernel exploit hints that lead to rabbit holes
- **Failing services** — MySQL that "crashes" and needs restart (`service mysql restart`), burning commands
- **Rate limiting / lockouts** — Failed SSH attempts trigger temporary lockout (30-60 seconds)
- **Timed events** — Cron jobs "about to run" that the attacker might wait for

### LLM-Specific Considerations
- LLMs have command budgets (max_session_length) — wasted commands = less real progress
- Connection resets force re-authentication (2-3 commands each time)
- Failing services trigger troubleshooting loops that can burn 5-10 commands

## Priority 5: Narrative / Social Engineering Bait

**Concept**: Plant stories and context that motivate deeper exploration.

- **Slack/email threads** in `/var/mail/` hinting at a "secret project" on another server
- **Incident response notes** — "We got hacked last month, all passwords changed" forcing attacker to search for new creds
- **Developer notes** — `TODO.md` files mentioning "move API keys to vault" (implies keys are still in files somewhere)
- **Scheduled deployments** — Cron jobs or CI pipelines that reference production credentials
- **Active user simulation** — `.bash_history` that looks fresh, recently modified files, login records in `last`

## Metrics to Add

- **Time per hop** — how long the LLM spends on each host before pivoting
- **Dead-end visits** — how many non-path hosts the attacker explores
- **Credential crack attempts** — commands related to password cracking (john, hashcat, base64, gpg)
- **Backtrack count** — how many times the attacker returns to a previously visited host
- **Command waste ratio** — commands on dead-end hosts vs. main-path hosts

## Implementation Order

1. **Password cracking on existing 3 hops** — add hashed/encrypted credentials alongside current plaintext breadcrumbs
2. **Dead-end hosts** — add 2-3 additional honeypot containers with no onward path
3. **Deeper per-host content** — expand filesystems and database content
4. **Dynamic stalling** — add latency, interruptions, and failing services
5. **Narrative bait** — enrich mail/notes/history with story elements
