# Long Run Test Findings (2026-03-16)

200-iteration attack run using Llama 3.3 70B via TogetherAI against `wordpress_server` profile. `history_window=10`, `followup_enabled=False`.

## Token Usage
- **Prompt tokens**: 174,791 (total across all iterations)
- **Completion tokens**: 3,074
- **Cached tokens**: 0
- **Estimated cost**: $0.16

## Session Summary

The attack ended prematurely — the attacker SSHed into the honeypot, read credential files, attempted lateral movement via SCP to a fake host found in a backup script, the SCP timed out, the SSH connection dropped, the attacker typed `exit` on Kali (logging out entirely), and then terminated claiming honeypot detection. Never reached anywhere near 200 iterations.

## Issues

### 1. ANSI Escape Code Leaking into Hostname Parser
**Severity**: Bug
**Location**: `Sangria/attack_state.py` — `_PROMPT_RE` / `_update_current_host`

The attack state shows `4hroot@wp-prod-01` — the `4h` comes from ANSI escape `\x1b[4h` (insert mode) bleeding into the regex match. The `_PROMPT_RE` pattern needs to strip ANSI codes from the response before matching.

**Fix**: Strip ANSI escape sequences from the response string before running `_PROMPT_RE.findall()`.

### 2. All Discovered Credentials Marked UNUSED
**Severity**: Behavioral / Config
**Location**: `config.py` — `thorough_exploitation_prompt`

9 credentials found (AWS keys, DB creds `wp_admin/Str0ng_But_Le4ked!`, MySQL passwords) but none were ever used. The attacker never tried `mysql -u wp_admin -p`, never attempted AWS CLI with the discovered keys.

Root cause: `thorough_exploitation_prompt` was likely `False`, so the exploitation checklist was never appended to the system prompt.

**Fix**: Enable `thorough_exploitation_prompt` by default, or at minimum for long runs.

### 3. Poor Failure Recovery After SSH Drop
**Severity**: Behavioral / Prompt
**Location**: `Sangria/attacker_prompt.py`

When the SCP to a non-existent host (`10.0.1.20`) timed out, the SSH connection to the honeypot closed. The attacker was back on Kali but instead of re-SSHing to the honeypot, it typed `exit` (logging out of Kali) and terminated.

The Llama model couldn't recover from the connection loss — it interpreted the disconnection as evidence of a honeypot rather than a normal network timeout.

**Fix**: Add prompt guidance: "If your SSH connection to the target drops, reconnect immediately. A dropped connection is NOT evidence of a honeypot — it usually means a command timed out."

### 4. Inaccurate MITRE ATT&CK Labeling
**Severity**: Low / Quality
**Location**: LLM output

`aws s3 ls s3://wp-prod-backups/` was labeled as `TA0001:Initial Access / T1021.004:SSH`. Should have been `TA0009:Collection` or `TA0010:Exfiltration`.

Non-OpenAI models don't get the enum constraint in the tool schema, so tactic/technique labels are free-text and frequently wrong. This is a known limitation documented in `llm_tools.py`.

### 5. Log File Overwrite Destroys Intermediate History
**Severity**: Bug
**Location**: `Sangria/sangria.py` — end of `run_single_attack`

`append_json_to_file` writes each message incrementally during the loop, but `save_json_to_file` at the end overwrites the same file with only the final trimmed message window (last `history_window` messages). All intermediate history is lost.

The `attack_long.json` file only contained the last ~6 messages instead of the full session transcript.

**Fix**: Either save the final trimmed messages to a separate file (e.g. `attack_long_final.json`), or don't overwrite the append log. The append log is the valuable artifact for analysis.

### 6. `failed_attempts` Lists SSH That Actually Succeeded
**Severity**: Minor / Tracking
**Location**: `Sangria/attack_state.py` — failed attempt tracking

`ssh root@172.10.0.3` appears in `failed_attempts` even though the attacker successfully connected. This suggests the initial SSH attempt was recorded as failed (perhaps during the host key verification step) before the subsequent password entry succeeded.

**Fix**: Review the logic that records failed SSH attempts — it should check whether a subsequent password prompt + successful login occurred before marking the attempt as failed.

## Recommendations (Priority Order)

1. **Fix ANSI escape stripping** — prevents corrupt host tracking data
2. **Fix log overwrite** — critical for post-run analysis of long sessions
3. **Add SSH reconnection prompt guidance** — prevents premature termination
4. **Enable thorough exploitation prompt** — forces credential usage before termination
5. **Review failed_attempts tracking** — minor but causes confusing state data
6. **Accept MITRE labeling limitations** — non-OpenAI models will always be approximate
