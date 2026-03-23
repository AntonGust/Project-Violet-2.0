# Long Run Fixes — Design Document

Fixes for the 6 issues found in the 200-iteration test run (`docs/doing/long-run-findings.md`).

## Fix 1: ANSI Escape Code Stripping

**Problem**: `_PROMPT_RE` matches ANSI escape remnants, producing corrupt hostnames like `4hroot@wp-prod-01` (the `4h` comes from `\x1b[4h` insert mode escape).

**Location**: `Sangria/attack_state.py` — `_update_current_host()`

**Design**: Add an ANSI stripping function and apply it before regex matching.

```python
# Module-level regex to strip ANSI escape sequences
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\[\?[0-9;]*[a-zA-Z]")

def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return _ANSI_RE.sub("", text)
```

Apply in `_update_current_host`:
```python
def _update_current_host(self, response: str):
    if not response:
        return
    clean = _strip_ansi(response)
    matches = _PROMPT_RE.findall(clean)
    ...
```

Also apply in `_parse_file_read` and `_extract_credentials_regex` since ANSI codes could corrupt credential extraction too.

**Scope**: Small — one utility function + 2-3 call sites.

---

## Fix 2: Log File Overwrite

**Problem**: `append_json_to_file` builds the full session log incrementally, but `save_json_to_file` at line 246 overwrites the same file with only the final trimmed message window. All intermediate history is lost.

**Location**: `Sangria/sangria.py` — end of `run_single_attack()`

**Design**: Save the final trimmed messages to a **separate** file, don't overwrite the append log.

```python
# Current (destructive):
save_json_to_file(messages_log_json, full_logs_path)

# Fixed:
final_path = full_logs_path.with_suffix(".final.json")
save_json_to_file(messages_log_json, final_path)
```

This gives us:
- `attack_1.json` — full incremental log (every message from every iteration)
- `attack_1.final.json` — final trimmed window (what the LLM saw on its last iteration)
- `attack_state_1.json` — structured state register (unchanged)

The `.final.json` is useful for debugging the LLM's last context. The main `.json` is the research artifact.

**Scope**: One-line change.

---

## Fix 3: SSH Reconnection Prompt Guidance

**Problem**: When the SSH connection dropped (SCP timeout), the Llama model interpreted the disconnection as honeypot evidence and terminated instead of reconnecting.

**Location**: `Sangria/attacker_prompt.py` — base prompt, `**IMPORTANT — Situational awareness:**` section

**Design**: Add a new bullet to the situational awareness section:

```
- If your SSH connection to the target drops (e.g. "Connection to X closed"), reconnect immediately
  by running `ssh user@host` again. A dropped connection is NOT evidence of a honeypot — it usually
  means a command timed out or the session was idle too long. Do not terminate because of a lost connection.
```

Also add to the Llama-specific addendum (`_ADDENDUM_LLAMA`) since this model is most prone to the issue:

```
- If you see "Connection to X closed" or return to the Kali prompt unexpectedly,
  SSH back to the target immediately. Do NOT type `exit` or call `terminate`.
```

**Scope**: Small — two text additions.

---

## Fix 4: Enable Thorough Exploitation by Default

**Problem**: 9 credentials found but none used. The `thorough_exploitation_prompt` config flag was `False`, so the exploitation checklist was never appended.

**Location**: `config.py` — line 38

**Design**: Change the default:

```python
# Before:
thorough_exploitation_prompt = False

# After:
thorough_exploitation_prompt = True
```

The `_THOROUGH_EXPLOITATION` block in `attacker_prompt.py` is already well-written and model-agnostic. It instructs the attacker to read credential files, connect to databases, use SSH keys, and not terminate until all credentials are tried.

Risk: adds ~150 tokens to every system prompt. At `history_window=10` this is negligible (~7% increase on a ~2000 token prompt).

**Scope**: One-line config change.

---

## Fix 5: Failed Attempts False Positive for SSH

**Problem**: `ssh root@172.10.0.3` appears in `failed_attempts` even though the attacker later authenticated successfully. This happens because the SSH handshake includes intermediate responses (host key verification, password prompt) that don't contain a shell prompt — but the `_parse_command` method also checks for `"Permission denied"` or `"Connection refused"` in the response.

The actual failure path: the first SSH command response contains the password prompt (`root@172.10.0.3's password:`), which doesn't trigger the failure check. But if there's any ANSI artifact or intermediate state that contains these strings, it falsely records a failure.

More likely: the attacker tried `ssh root@172.10.0.3` (port 22, default) first, which would get `Connection refused` because Cowrie only listens on port 2222. Then tried `ssh root@172.10.0.3 -p 2222` which succeeded. Both are recorded as separate commands, but `failed_attempts` doesn't remove entries when a later attempt to the same host succeeds.

**Location**: `Sangria/attack_state.py` — `_parse_command()` failed attempts block and `_parse_ssh()`

**Design**: When SSH succeeds, remove any prior failed attempts to the same host:

```python
def _parse_ssh(self, command: str, response: str):
    ...
    if succeeded:
        host.visited = True
        host.access_level = access
        host.access_method = f"SSH {user} port {port}"

        # Clear failed attempts for this host (earlier attempts may have failed)
        self.failed_attempts = [
            a for a in self.failed_attempts
            if target_ip not in a
        ]

        # Mark any matching credentials as used
        ...
```

**Scope**: Small — 3-line addition.

---

## Fix 6: MITRE ATT&CK Labeling (Accept Limitation)

**Problem**: Non-OpenAI models produce inaccurate tactic/technique labels because they get free-text fields instead of enum constraints.

**Design**: No code change. This is a known trade-off documented in `llm_tools.py`. Enum constraints for non-OpenAI models would add ~2000 tokens to every tool call schema, which is not worth the marginal improvement in labeling accuracy.

**Optional future enhancement**: Post-process labels in `attack_state.py` — maintain a lookup table of common commands → correct MITRE mappings and auto-correct obvious mismatches. Low priority.

---

## Implementation Order

| # | Fix | Files | Effort | Risk |
|---|-----|-------|--------|------|
| 1 | ANSI stripping | `attack_state.py` | Small | None |
| 2 | Log overwrite | `sangria.py` | One line | None |
| 3 | SSH reconnection prompt | `attacker_prompt.py` | Small | None |
| 4 | Enable thorough exploitation | `config.py` | One line | Low — adds ~150 tokens to prompt |
| 5 | Failed attempts cleanup | `attack_state.py` | Small | None |
| 6 | MITRE labeling | — | None | — |

All fixes are independent and can be implemented in any order. Total: ~30 lines of code across 4 files.
