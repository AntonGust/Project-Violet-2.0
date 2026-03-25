# Design: Honeypot Hardening Agent

A Claude Code skill that orchestrates an automated **run → analyze → fix → verify** loop to continuously harden Cowrie honeypot profiles until they pass attack simulation without authenticity issues.

---

## Problem

Running the Project Violet attack loop, analyzing logs, identifying honeypot-detection triggers, implementing fixes, and re-verifying is currently a fully manual process. Each cycle requires:

1. Configuring and launching `main.py`
2. Watching for SSH failures, command errors, or early termination
3. Reading through `cowrie.json` and `attack_*.json` logs
4. Identifying what broke (missing commands, wrong output, credential gaps, etc.)
5. Writing fixes in Cowrie handlers, profiles, or prompt config
6. Re-running to verify

This takes hours per profile. With 13 profiles, manual hardening doesn't scale.

---

## Solution: `/sc:harden` Skill

A Claude Code skill that automates the cycle with human-in-the-loop confirmation at each fix step.

### Flow

```
┌──────────────────────────────────────────────────┐
│                  /sc:harden                       │
│                                                   │
│  1. SELECT PROFILE                                │
│     └─ User picks or cycles through profiles      │
│                                                   │
│  2. RUN ATTACK LOOP ◄──────────────────────┐      │
│     ├─ Start Docker (docker compose up)    │      │
│     ├─ Launch main.py (single session)     │      │
│     ├─ Monitor stdout for fatal signals    │      │
│     └─ Capture exit code + logs            │      │
│                                            │      │
│  3. ANALYZE RESULTS                        │      │
│     ├─ Parse cowrie.json events            │      │
│     ├─ Parse attack_*.json LLM transcript  │      │
│     ├─ Parse attack_state_*.json           │      │
│     ├─ Categorize findings:               │      │
│     │   ├─ FATAL: SSH/Docker failures      │      │
│     │   ├─ COMMAND: missing/wrong output   │      │
│     │   ├─ PROMPT: behavioral issues       │      │
│     │   └─ PROFILE: missing files/services │      │
│     └─ Produce findings report             │      │
│                                            │      │
│  4. PRESENT TO USER                        │      │
│     ├─ Show what worked                    │      │
│     ├─ Show what failed + why              │      │
│     ├─ Show proposed fixes                 │      │
│     └─ Ask for confirmation                │      │
│                                            │      │
│  5. IMPLEMENT FIXES                        │      │
│     ├─ Apply approved fixes                │      │
│     └─ Skip rejected fixes                 │      │
│                                            │      │
│  6. VERIFY ────────────────────────────────┘      │
│     └─ Re-run with SAME profile                   │
│        to confirm fixes work                      │
│                                                   │
│  7. CONTINUE or FINISH                            │
│     ├─ If new issues found → back to step 3       │
│     ├─ If clean run → report success               │
│     └─ User can switch to next profile             │
└──────────────────────────────────────────────────┘
```

---

## Phase Details

### Phase 1: Profile Selection

The skill accepts a profile name or path as argument:
```
/sc:harden wordpress_server
/sc:harden Reconfigurator/profiles/backup_server.json
```

If no argument, show the list of 13 profiles and ask user to pick.

Config overrides for hardening mode:
- `num_of_sessions = 1` (single session per run — enough to surface issues)
- `max_session_length = 200` (full-length session to surface all issues)
- `honeynet_enabled = True` (test with full honeynet)
- `reconfig_method = ReconfigCriteria.NO_RECONFIG` (keep the same profile)
- `followup_enabled = False` (save tokens)
- `thorough_exploitation_prompt = True` (exercise more commands)

### Phase 2: Run Attack Loop

**Execution method:** Run `main.py` via subprocess with output capture.

**Graceful stop triggers** — monitor stdout/stderr for:

| Signal | Category | Action |
|--------|----------|--------|
| `Connection refused` on initial SSH | FATAL | Stop immediately, report Docker/Cowrie not ready |
| `Permission denied (publickey)` repeated 3x | FATAL | Stop, report credential mismatch |
| `pexpect.exceptions.TIMEOUT` | FATAL | Stop, report SSH hung |
| `docker compose` exit code != 0 | FATAL | Stop, report Docker failure |
| `Connection reset by peer` | FATAL | Stop, report Cowrie crash |
| `***COMMAND TOOK TOO LONG***` 3+ times | WARN | Let run finish, flag timeout pattern |
| `command not found` | ISSUE | Let run finish, flag missing command |
| `I'm sorry, but I can't help` | BEHAVIORAL | Stop, report model refusal |
| Python traceback in stderr | FATAL | Stop, capture traceback |

**Log collection after run:**
- `cowrie_config/var/log/cowrie/cowrie.json` — honeypot events
- `Experiments/{name}/hp_config_1/full_logs/attack_1.json` — full LLM transcript
- `Experiments/{name}/hp_config_1/attack_state_1.json` — structured state
- stdout/stderr capture from the run itself

### Phase 3: Analyze Results

This is the core intelligence of the agent. It reads the logs and produces a structured findings report.

**Analysis dimensions:**

#### A. Command Success Rate
Parse `cowrie.json` for `cowrie.command.input` events. For each command:
- Did it produce output? (check for corresponding `cowrie.command.output` or `cowrie.log.closed`)
- Was it a `command not found`?
- Did it timeout?
- Was the output consistent with the profile? (compare `ps` output vs profile services, `ls` vs directory_tree, etc.)

#### B. Authenticity Gaps
Cross-reference command outputs with profile data:
- `ps aux` output matches `profile.services`?
- `ls /path` output matches `profile.directory_tree`?
- `cat /file` output matches `profile.file_contents`?
- `ss -tlnp` / `netstat` matches `profile.services` ports?
- `systemctl status X` consistent with running services?
- `crontab -l` matches `profile.crontabs`?
- `df -h` matches `profile.disk_layout`?
- `id` / `whoami` matches `profile.users`?

#### C. Behavioral Analysis
From the LLM transcript (`attack_*.json`):
- Did the attacker discover the honeypot? (check `terminate` call's `success` field)
- What triggered honeypot suspicion? (look for reasoning about inconsistencies)
- Did the attacker get stuck in loops? (repeated commands)
- Did credentials get used? (check attack_state unused credentials)
- Was lateral movement attempted?

#### D. Infrastructure Issues
- Docker startup time
- SSH connection stability
- Command response latency (from timing data in display output)
- Cowrie errors in `cowrie.json`

**Findings report format:**

```markdown
## Hardening Report: {profile_name} — Run #{n}

### What Worked
- SSH connection established successfully
- 23/30 commands returned profile-consistent output
- Credential lures discovered in /var/www/wp-config.php
- Attacker spent 45 iterations before terminating

### Issues Found

#### FATAL (blocked the run)
None

#### COMMAND ISSUES (wrong/missing output)
1. `systemctl status nginx` — returned LLM hallucination instead of profile-aware output
   - Expected: active (running), PID from profile services
   - Got: generic systemd output with wrong PID
   - Fix: Verify systemctl handler reads this profile's services correctly

2. `grep -r password /etc/` — returned hallucinated file paths
   - Files mentioned in grep output don't exist in directory_tree
   - Fix: Ensure grep handler walks pickle filesystem

#### BEHAVIORAL ISSUES
1. Attacker detected honeypot via `df -h` inconsistency
   - Profile shows 500G /var/backups but df showed generic 200G
   - Fix: Update profile disk_layout or df txtcmd

#### PROFILE GAPS
1. No `.bash_history` for user `deploy` — attacker noticed empty history
   - Fix: Add realistic bash_history to profile
```

### Phase 4: Present to User

Display the findings report in the terminal. For each issue with a proposed fix, ask:
- **Implement this fix?** [Y/n]
- Group related fixes (e.g., all profile JSON changes together)

### Phase 5: Implement Fixes

Fix categories and implementation approach:

| Category | Implementation |
|----------|---------------|
| Profile JSON gaps | Edit `Reconfigurator/profiles/{name}.json` — add missing files, services, crontabs |
| Cowrie command handler bugs | Edit handler in `Cowrie/cowrie-src/src/cowrie/commands/` |
| New command handler needed | Create new handler file, register commands |
| Prompt/behavioral issues | Edit `Sangria/attacker_prompt.py` or `config.py` |
| txtcmd fixes | Edit `Reconfigurator/profile_converter.py` or txtcmd files directly |
| Docker/infra issues | Edit `docker-compose.yml` or `cowrie.cfg` |

After implementing, regenerate the profile's deployment artifacts:
```python
# Regenerate fs.pickle, honeyfs, txtcmds from updated profile
python -c "from Reconfigurator.profile_converter import deploy_profile; deploy_profile('path/to/profile.json', 'cowrie_config')"
```

### Phase 6: Verify

Re-run the attack loop with the same profile and same config overrides. Compare the new findings report against the previous one:
- Issues that are now resolved → mark as FIXED
- New issues that appeared → flag as REGRESSION
- Remaining issues → carry forward

### Phase 7: Continue or Finish

After verification:
- If issues remain and user wants to continue → loop back to Phase 3
- If clean run (no COMMAND or FATAL issues) → declare profile hardened
- User can switch to the next profile: `/sc:harden mail_server`

---

## Implementation: Claude Code Skill

### Skill File Structure

Since Claude Code skills are prompt-based (not executable scripts), the skill orchestrates by instructing Claude to use its tools in sequence.

**File:** `.claude/skills/sc-harden.md`

The skill prompt instructs Claude to:

1. Read the target profile JSON
2. Set config overrides (edit `config.py` temporarily or use env vars)
3. Run `python main.py` via Bash tool with timeout
4. Monitor output, kill on FATAL signals
5. Read log files after run completes
6. Analyze logs against profile data
7. Present findings
8. On confirmation, edit files to fix issues
9. Re-run and compare

### Key Design Decisions

**Why a skill, not a Python script?**
- The analysis requires LLM reasoning (understanding *why* output is wrong, proposing *how* to fix it)
- Fixes span multiple file types (JSON profiles, Python handlers, config files) — Claude already knows how to edit all of these
- The human-in-the-loop confirmation is natural in Claude Code's interactive mode
- A Python script would need its own LLM integration for analysis, duplicating what Claude already does

**Why single-session runs?**
- One session (50 iterations max) is enough to surface command/authenticity issues
- Multiple sessions waste tokens on the same profile without finding new issues
- Keeps the feedback loop tight: run → fix → rerun in ~5 minutes per cycle

**Why not use sc:analyze and sc:implement directly?**
- Those skills are designed for general-purpose analysis and implementation
- The hardening agent needs domain-specific analysis (cross-referencing commands against profile data)
- Better to have a single orchestrating skill that knows the full context
- The agent can internally use the same patterns those skills use, but tailored to honeypot hardening

**Temporary config changes:**
- Save original `config.py` values before overriding
- Restore after hardening session ends (or on Ctrl+C)
- Alternative: use a separate `config_harden.py` that imports and overrides `config`

**Session isolation:**
- Each hardening run uses a unique `experiment_name` like `Harden_{profile}_{timestamp}`
- Logs don't collide with production experiment data
- Old hardening logs can be cleaned up periodically

---

## Stopping Criteria

The agent considers a profile "hardened" when:

1. **No FATAL issues** — attack loop runs to completion
2. **No COMMAND issues** — all commands return profile-consistent output
3. **No obvious authenticity gaps** — attacker doesn't detect honeypot due to output inconsistencies
4. **Credentials get used** — the attack_state shows discovered credentials marked as USED
5. **Reasonable session length** — attacker runs 30+ iterations before terminating (not bailing early due to confusion)

Note: The attacker *may* still detect the honeypot for legitimate reasons (e.g., noticing no real network traffic, or the filesystem being too clean). That's fine — the goal is to eliminate *fixable* tells, not make the honeypot undetectable.

---

## Risk & Limitations

- **Token cost:** Each run costs ~$0.15-0.30 (Llama 3.3 70B via TogetherAI). A full hardening session (3-5 cycles) costs ~$1-2 per profile.
- **Time:** Each cycle takes ~5-10 minutes (Docker startup + 50 iterations + analysis). Budget 30-60 minutes per profile.
- **False positives:** The agent may flag LLM hallucination inconsistencies that are actually fine (e.g., slightly different timestamp formats). User review at Phase 4 catches these.
- **Cowrie source changes:** Fixes to command handlers require rebuilding the Cowrie Docker image. The skill should detect when handler files were modified and prompt for `docker compose build`.
- **Model variability:** Different attacker LLMs exercise different commands. A profile hardened against Llama 3.3 may have issues with GPT-4 or DeepSeek. Consider running with multiple models for thorough hardening.

---

## Future Extensions

- **Profile rotation:** Automatically cycle through all 13 profiles in sequence
- **Regression suite:** Save "known good" attack transcripts and diff against new runs
- **Authenticity score:** Quantify how many commands returned consistent vs inconsistent output
- **Multi-model hardening:** Run the same profile against 2-3 different attacker models
- **CI integration:** Run hardening checks as part of PR review for profile/handler changes
