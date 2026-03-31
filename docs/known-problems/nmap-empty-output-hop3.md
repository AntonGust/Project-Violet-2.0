# nmap Returns Empty Output on Hop 3

**Priority:** P2 (medium)
**Found:** 2026-03-30 hardening run v2 (wordpress_server profile, hop 3 = cicd_runner)
**Status:** Open — needs investigation

## Problem

`nmap -sn 172.10.0.0/24 2>/dev/null | head -30` on hop 3 (ci-runner-07) returned empty output. The Cowrie JSON log shows `cowrie.command.failed` for the command.

The `nmap.py` command handler exists in `Cowrie/cowrie-src/src/cowrie/commands/nmap.py` and is registered in prequery's `_COMMAND_FAMILIES`. The handler was created as part of the wordpress hardening fixes.

## Possible Causes

1. **Docker image cache** — The Cowrie Docker image may have been built from cache before `nmap.py` was added. A forced rebuild (`docker compose build --no-cache`) may fix this.
2. **Pipeline interference** — The `2>/dev/null | head -30` suffix may cause Cowrie's shell to split the command before the nmap handler gets invoked. The nmap handler may run but its output gets lost in the pipe.
3. **Handler not discovered** — Cowrie's command loader may not be finding `nmap.py` if the module isn't properly importable inside the Docker container's Python environment.

## How to Investigate

1. Run `docker compose exec cowrie_hop3 python3 -c "from cowrie.commands.nmap import commands; print(commands)"` to check if the handler loads.
2. Test with a simple `nmap --version` (no pipes/redirects) to isolate the issue.
3. Check Cowrie's startup logs for import errors: `docker compose logs cowrie_hop3 2>&1 | grep -i nmap`.
4. Try `docker compose build --no-cache cowrie_hop3` and re-test.

## Files

- Handler: `Cowrie/cowrie-src/src/cowrie/commands/nmap.py`
- Prequery registration: `Cowrie/cowrie-src/src/cowrie/shell/prequery.py` (line ~51, ~116)
