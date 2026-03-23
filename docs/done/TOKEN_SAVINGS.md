# Token Savings Plan

## Context

Measured from session 2 log (Llama 3.3 70B via Together AI, ~10 iterations, 21 API calls):
- Total prompt tokens sent: **63,367**
- Total completion tokens: **881**
- Cached tokens: **0** (Together AI doesn't support prompt caching)
- Cost: ~$0.056 prompt + ~$0.001 completion

---

## Opportunity 1: Disable Follow-up Call — **47% prompt token savings** ✅ IMPLEMENTED

**File:** `Sangria/sangria.py` lines 176-218, `config.py` line 37

**Current behavior:** After every tool execution, a second "followup" API call re-sends the entire conversation to extract narrative/reasoning text from the model.

**Real-world results:**
- Followup calls consumed: **~29,967 prompt tokens** (47% of total)
- Followup content produced: **2 messages** total, both just "The operation is now terminated."
- The other ~8 followup calls produced **nothing useful**

**Why it's wasteful:** The model already provides reasoning via `message.content` alongside `tool_calls`. The next decision call (line 117) naturally forces the model to reason about the tool output before choosing its next action. The followup is redundant.

**Implementation:**
- `config.py`: Added `followup_enabled = False` toggle (line 37)
- `sangria.py`: Wrapped followup block with `if tool_use and config.followup_enabled:`
- Added fallback iteration timing when followup is disabled so per-iteration timing still prints

**Savings:** ~47% of prompt tokens, ~50% of API calls, ~30-40% wall-clock time per session.

**Risk:** Low. The model reasons naturally in the next decision call. Followup was originally added for OpenAI to force pure-text output, but even there `message.content` already contains reasoning alongside tool calls. Set `followup_enabled = True` to restore old behavior.

---

## Opportunity 2: Message History Trimming + Attack State Register — **75-92% at depth >50** ✅ IMPLEMENTED

**File:** `Sangria/attack_state.py` (new), `Sangria/sangria.py`, `config.py`, `main.py`

**Previous behavior:** The full message history was sent with every API call. At iteration 200, that's ~60K context tokens per call. Naively trimming old messages would destroy the model's memory of hosts, credentials, and files.

**Implementation:**
- `Sangria/attack_state.py`: New `AttackStateRegister` class tracking hosts, credentials, files, services, and failed attempts. Profile-aware credential detection (zero false positives for known files) with regex fallback. Capped at 50 entries per category with deduplication.
- `Sangria/sangria.py`: State register initialized with honeypot profile at session start. Updated after every tool call. Injected into system prompt each iteration. Sliding window trims old messages when `history_window > 0`.
- `config.py`: Added `history_window = 0` (disabled by default; set to 10-20 to enable trimming).
- `main.py`: Both call sites pass `profile=` to `run_single_attack`.
- Attack state saved to `attack_state_N.json` alongside session logs for post-session analysis.

**To enable:** Set `history_window = 10` (or similar) in `config.py`. The state register is always active for logging; trimming only happens when `history_window > 0`.

**Savings by session depth (with `history_window = 10`):**

| Depth | Current | With state register + window=10 | Savings |
|-------|---------|--------------------------------|---------|
| 10 iterations | ~4,200 tokens/call | ~3,500 tokens/call | 17% |
| 50 iterations | ~16,200 tokens/call | ~4,000 tokens/call | 75% |
| 100 iterations | ~31,200 tokens/call | ~4,500 tokens/call | 86% |
| 200 iterations | ~61,200 tokens/call | ~5,000 tokens/call | 92% |

**Risk:** Medium. Mitigated by the state register preserving all critical information. `history_window = 0` (default) disables trimming entirely for safe rollout.

---

## Opportunity 3: Tighter Output Truncation — **10-20% for verbose commands** ✅ IMPLEMENTED

**File:** `Sangria/terminal_io.py` line 293

**Previous:** Truncated tool output at 10,000 characters (~2,500 tokens). This large output is then re-sent with every subsequent API call.

**Implementation:** Reduced threshold from 10,000 → 5,000 characters (~1,250 tokens):

```python
if len(command_response) > 5000:
    command_response = command_response[-5000:] + "\n***TOO LONG OUTPUT FROM COMMAND, ONLY SHOWING THE FINAL 5000 characters***"
```

**Savings:** ~10-20% for sessions with verbose commands (nmap, find, cat on large files).

**Risk:** Low. Commands producing >5,000 chars of output are typically scans or file listings where only the tail matters. The model rarely references early output lines.

---

## Opportunity 4: OpenAI Prompt Caching (already available)

**Current:** When using OpenAI (`llm_provider = "openai"`), the session 2 log shows 0% cached tokens. However, OpenAI automatically caches matching prompt prefixes.

**Why 0% in log:** Session 2 used Together AI, which doesn't support prompt caching. When using OpenAI, the system prompt + tool schemas (~1,200 tokens) would be cached after the first call, saving ~$0.75/1M on subsequent calls.

**No code change needed.** This works automatically when `llm_provider = "openai"`. Just documenting that OpenAI sessions are already cheaper per-token due to prefix caching.

---

## Summary

| # | Opportunity | Tokens saved | Effort | Risk | Status |
|---|-------------|-------------|--------|------|--------|
| 1 | **Disable followup call** | ~47% of total | Low (config flag) | Low | ✅ Done |
| 2 | **State register + history trimming** | ~75-92% at depth >50 | Medium | Medium | ✅ Done |
| 3 | **Tighter output truncation** | ~10-20% for verbose cmds | Low (change constant) | Low | ✅ Done |
| 4 | OpenAI prompt caching | Automatic | None | None | N/A (automatic) |

## Implementation Order

1. ~~**Followup toggle** — biggest immediate impact, simplest change~~ ✅
2. ~~**Output truncation** — small change, immediate benefit~~ ✅
3. ~~**Attack State Register** (`ATTACK_STATE_REGISTER.md`) — prerequisite for history trimming~~ ✅
4. ~~**History window trimming** — depends on #3, biggest long-term benefit for deep sessions~~ ✅
