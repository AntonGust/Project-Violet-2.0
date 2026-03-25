# Cowrie Fake SSH Loopback — Attacker Gets Stuck on Hop 1

## Status: Open

## Problem

When the attacker runs `ssh user@<internal-ip>` from inside hop 1, Cowrie intercepts the command, fakes a new SSH session (accepts any password), and drops the attacker into a **new shell that's still hop 1** — but with prompt `root@localhost:~#` instead of `root@wp-prod-01:~#`.

Each fake SSH creates a new Cowrie session ID, which the session correlator counts as a separate "journey." In the 2026-03-24 hardening run, this produced 5 apparent sessions when there were zero actual disconnects.

## Observed Behavior (Harden_wordpress_server 2026-03-24)

| Session | Trigger | Result |
|---------|---------|--------|
| 1 | Legitimate initial SSH to hop 1 | `deploy@wp-prod-01` |
| 2 | `ssh deploy@10.0.1.20` from hop 1 | Fake SSH, loops back as `root@localhost` |
| 3 | `ssh backupd@10.0.1.100` from hop 1 | Fake SSH, loops back again |
| 4 | `ssh deploy@10.0.1.20` (repeated) | LLM forgot it tried this |
| 5 | Stays on hop 1 after more failed attempts | Re-explores same files |

The attacker repeated identical recon commands (`cat /var/www/html/.env`, `cat /var/backups/credentials.old`, etc.) **5 times**.

## Root Cause

Two interacting issues:

### 1. Cowrie's built-in SSH handler fakes connections to unknown IPs

Cowrie's SSH command handler intercepts SSH commands before our proxy code runs for internal IPs like `10.0.1.20` and `10.0.1.100`. Instead of returning "Connection refused" or routing to the real next-hop container, it creates a fake session that loops back to the same honeypot.

The SSH simulated fallback fix (2026-03-24) handles `CONNECT_UNREACHABLE` from the proxy, but Cowrie's built-in handler takes precedence for these IPs.

### 2. History windowing causes LLM to forget prior exploration

`history_window = 40` in `config.py` trims old messages. After each fake SSH "hop," the LLM loses context of earlier exploration and re-runs the same commands. The `AttackStateRegister` doesn't include strong enough signals about which hosts have been fully explored.

## Proposed Fixes

### Fix 1 (Primary): Route or reject SSH to internal IPs properly

Ensure that SSH to internal IPs either:
- Routes to the actual next-hop Cowrie container (via the proxy) if credentials match
- Returns a proper error ("Connection refused" / "No route to host") if the target isn't reachable

This requires understanding how Cowrie's SSH command handler decides whether to proxy vs fake, and making our proxy logic take priority.

### Fix 2 (Secondary): Strengthen AttackStateRegister exploration tracking

Add stronger signals to the attack state about which hosts have been fully explored, so the LLM doesn't repeat the same recon after a history window trim. For example, a `fully_explored` flag or a summary of files already read per host.

## Related Files

- `Cowrie/cowrie-src/src/cowrie/commands/ssh.py` — SSH command handler
- `Cowrie/cowrie-src/src/cowrie/commands/ssh_proxy.py` — SSH proxy session (3-value return)
- `Sangria/attack_state.py` — AttackStateRegister, hostname tracking
- `config.py` — `history_window = 40`
- `Purple/session_correlator.py` — Journey tracking

## Related Changes

- 2026-03-24: SSH simulated fallback (3-value return from ssh_proxy.py)
- 2026-03-24: Hostname tracking fix (removed fallback iteration)
