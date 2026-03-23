# Design: MySQL Interactive Handler + Model-Specific Attacker Prompts

## Problem Summary

From session 2 analysis:
1. **MySQL returns empty/fails silently** — attacker runs `mysql -u root -p`, enters password, gets nothing useful
2. **Attacker terminates prematurely** — extracts 3 of 12+ available secrets, then quits
3. **0 honeypot LLM fallback calls** — commands either hit native handlers or empty txtcmds
4. **Same prompt for all models** — Llama/DeepSeek models need different guidance than OpenAI models (loop avoidance, stricter tool-call formatting, more explicit exploration checklists)

---

## Solution 1: Native MySQL Command Handler ✅ IMPLEMENTED

Implemented in `Cowrie/cowrie-src/src/cowrie/commands/mysql.py`. Registered in `commands/__init__.py`.

**What's done:**
- Manual arg parsing for `-u`, `-p` (with real MySQL's no-space quirk), `-h`, `-D`, `-e`, `--help`, `--version`
- Password prompt via `password_input` + `callbacks` pattern (same as ssh.py/su.py), always accepts
- Interactive `mysql>` shell loop with `USE db` prompt tracking (`mysql [dbname]>`)
- SQL routed to LLM fallback via `handle_command(f"mysql -e '{sql}'")` using Deferred pattern
- Inline `-e` queries execute immediately without interactive mode
- Async guard (`_llm_pending` + `protocol.llm_pending`) prevents input during LLM calls
- Ctrl-C shows new prompt, Ctrl-D exits with "Bye"
- Registered as `/usr/bin/mysql`, `/usr/local/bin/mysql`, and `mysql`
- MySQL version pulled from profile services

---

## Solution 2: Model-Specific Attacker Prompts ✅ IMPLEMENTED

Implemented in `Sangria/attacker_prompt.py`.

**What's done:**
- `_get_model_family()` classifier: maps `config.llm_model_sangria` → `openai`/`llama`/`deepseek`/`qwen`/`default`
- Per-family addenda appended to prompt: anti-loop rules (Llama), action-over-reasoning (DeepSeek), explicit tool arg names (Qwen), empty (OpenAI), conservative fallback (default)
- `_THOROUGH_EXPLOITATION` section with detailed credential checklist — **opt-in** via `config.thorough_exploitation_prompt = False` (off by default to avoid over-guiding the attacker)
- `get_prompt()` signature unchanged — no breaking changes
- Prompt branches on **model name** (not provider), so Llama on Together AI gets Llama guidance

---

## Solution 3: Fix LLM Fallback Bypass ✅ RESOLVED BY SOLUTION 1

No additional code changes needed. The `Command_mysql` registration (Solution 1) hits step 1 of `getCommand()` lookup (`self.commands[cmd]`) before filesystem/txtcmd resolution. The original silent-failure path is completely bypassed. The MySQL handler also provides a graceful error (`ERROR 2002 ... Can't connect`) if no `llm_fallback_handler` is available.

---

## Solution 4: OpenAI Tool-Calling Correctness Audit ✅ IMPLEMENTED

All three issues fixed in `Sangria/llm_tools.py` and `Sangria/sangria.py`.

**What's done:**
- **Issue 1** — `terminate` tool schema now gets `strict: True` + `additionalProperties: False` when `is_openai`, matching `terminal_input`
- **Issue 2** — `honeypot_logs` no longer injected into the API message dict. A separate `log_entry` dict (with `honeypot_logs` and `name`) is written to the file log; only the clean `tool_response` goes into `messages`
- **Issue 3** — Deprecated `name` field removed from `tool_response`. Kept in `log_entry` for file log debugging only

---

## Solution 5: Attack State Register ✅ IMPLEMENTED

Implemented in `Sangria/attack_state.py`. See `docs/done/ATTACK_STATE_REGISTER.md` and `docs/done/TOKEN_SAVINGS.md` for full details.

**What's done:**
- `AttackStateRegister` class tracking hosts, credentials, files, services, failed attempts
- Profile-aware credential detection with regex fallback
- System prompt injection each iteration (~300-500 tokens regardless of session depth)
- Sliding window history trimming (`config.history_window = 10`)
- Attack state saved to `attack_state_N.json` per session
- Followup call toggle (`config.followup_enabled = False`) — 47% prompt token savings
- Output truncation reduced from 10,000 → 5,000 chars

**Relationship to remaining solutions:**
- **Solution 2 (prompt addenda):** The state register's `HOSTS:` section now shows visited hosts explicitly, making Llama's "NEVER SSH to the same host twice" rule less load-bearing. Still worth implementing as belt-and-suspenders.
- **Solution 4, Issue 2 (`honeypot_logs`):** The state register's `update_from_tool_call()` parses tool responses. Fixing the `honeypot_logs` leak (separating log-only fields from API messages) improves parsing reliability.

---

## Implementation Order

1. ~~**OpenAI tool-calling fixes** (`Sangria/llm_tools.py`, `Sangria/sangria.py`) — quick wins, fixes strict mode gap and message hygiene~~ ✅
2. ~~**MySQL command handler** (`Cowrie/cowrie-src/src/cowrie/commands/mysql.py`) — highest impact, direct fix for silent failure~~ ✅
3. ~~**Model family classifier + prompt addenda** (`Sangria/attacker_prompt.py`) — prevents premature termination, compensates for model-specific weaknesses~~ ✅
4. ~~**Attack State Register** (`Sangria/attack_state.py`) — structured memory for long sessions and honeynet runs~~ ✅
5. ~~**Fix LLM Fallback Bypass** — resolved by Solution 1~~ ✅
6. ~~**Verify LLM fallback config** — ensure hybrid_llm is enabled and API key is set~~ ✅ Verified: all cowrie configs have `[hybrid_llm] enabled = true`, API key passed via `COWRIE_HYBRID_LLM_API_KEY` env var in docker-compose
