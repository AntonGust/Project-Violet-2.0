# RAG-Based Response Caching for Cowrie LLM Fallback

## The Core Insight

Cowrie has two response layers:

1. **Deterministic layer** — `txtcmds/` (static outputs for `uname`, `ps`, `df`, etc.) + `honeyfs/` (file contents for `cat`) + pickle filesystem (for `ls`, `cd`). **Zero LLM cost.**
2. **LLM fallback** — everything else goes through `llm_fallback.py`. **This is where all honeypot tokens are spent.**

The idea: **grow the deterministic layer automatically using LLM outputs as training data**. After enough sessions, most commands have been seen before and can be served from cache. The LLM fallback fires less and less.

This is `txtcmds` on steroids.

## Where This Works Brilliantly

**Stateless, read-only commands on the same profile** — the low-hanging fruit:

```
nmap localhost          → always the same open ports
dpkg -l                 → always the same package list
systemctl status nginx  → always the same service status
cat /etc/crontab        → always the same crontab
ip addr                 → always the same network config
netstat -tlnp           → always the same listeners
```

These commands are asked in nearly every session. After 10-20 sessions on the same profile, 80%+ of recon commands have been seen. Cache hit rate would be very high.

**Attacker command patterns are highly repetitive.** The Discovery phase (TA0007) dominates early sessions. Every attacker runs some variant of `ls`, `cat /etc/passwd`, `uname -a`, `whoami`, `id`, `ps aux`, `netstat`. These are already partially covered by txtcmds, but the LLM still handles many variations.

## Where This Breaks Down

### 1. Session state makes responses context-dependent

The `llm_fallback.py` has a `SessionStateRegister` that tracks per-session modifications. If an attacker runs:
```
mkdir /tmp/backdoor
echo "malware" > /tmp/backdoor/payload.sh
ls /tmp/backdoor
```

The `ls /tmp/backdoor` response depends on what happened *earlier in this session*. A cached response from a different session wouldn't reflect the attacker's modifications. This is fundamentally non-cacheable.

### 2. Pre-query context varies per profile

The same command produces different responses on different profiles:
- `systemctl status apache2` on the WordPress profile → running
- `systemctl status apache2` on the CI/CD profile → not found

So the cache key must include the profile, not just the command.

### 3. Some commands need temporal variation

`date`, `uptime`, `w`, `last` — these should show different values. Identical timestamps across sessions are a honeypot tell.

### 4. The LLM's "personality" matters for deception

Subtle variation in responses makes the honeypot more convincing. If `apt install nmap` returns the exact same output character-for-character every time, a sophisticated attacker might notice.

## Will LLM Calls Reach Zero?

**No — but they could drop 70-90% on a mature profile.** Here's why:

| Command type | % of commands | Cacheable? |
|---|---|---|
| Recon/discovery (ls, cat, ps, netstat, etc.) | ~40% | Yes — already partially in txtcmds |
| Service interaction (mysql, curl, wget) | ~20% | Mostly yes — stateless queries |
| File creation/modification (echo, mkdir, chmod) | ~15% | No — session-state dependent |
| Package management (apt, pip, npm) | ~10% | Mostly yes — install outputs are predictable |
| Novel/creative commands | ~15% | No — requires LLM reasoning |

The remaining 15-30% of commands that genuinely need the LLM are the interesting ones — the attacker trying something creative, building exploit chains, or interacting with session-specific state. These are also the commands where a convincing LLM response matters most.

## RAG vs. Exact-Match Cache

RAG is smarter than exact-match because:

- `ls -la /root` and `ls -al /root` and `ls --all -l /root` → same response needed
- `cat /etc/passwd` and `head -50 /etc/passwd` → similar enough
- `apt install nmap` and `apt-get install nmap` → same output

BAAI/bge-m3 embeddings are already in the stack. An embedding-based lookup with similarity threshold could handle command variations without needing exact string matching.

But there's a simpler alternative worth considering: **command normalization + exact match**. Normalize the command (sort flags, resolve aliases, strip whitespace) and do a dictionary lookup. This is faster, deterministic, and avoids the failure modes of semantic similarity (where two commands *look* similar but produce different outputs).

A hybrid approach might be best: normalize first, try exact match, fall back to embedding similarity, fall back to LLM.

## The Bigger Picture — Self-Improving Honeypot

This idea has a deeper implication: **the honeypot gets more realistic over time**. Early sessions have slow, inconsistent LLM responses. After hundreds of sessions, the cached responses are instant and consistent. The honeypot becomes harder to detect because:

1. Response latency drops (no LLM round-trip)
2. Responses are proven to be convincing (they didn't cause early termination in past sessions)
3. Coverage grows — fewer "I don't understand that command" failures

Cached responses could even be scored by whether the attacker continued or terminated after receiving them, preferring responses that kept the attacker engaged longer.

---

## Requirements Specification

### Goal

Reduce LLM token consumption on the honeypot side by caching LLM-generated responses and serving them for repeated/similar commands, while maintaining deception quality.

### Functional Requirements

**FR-1: Response cache storage**
- Store LLM-generated responses keyed by (profile_id, normalized_command)
- Each cache entry stores: command, response, profile_id, timestamp, hit_count, session_outcome (continued/terminated)
- Persistent storage across experiment runs (SQLite or JSON files per profile)

**FR-2: Command normalization**
- Normalize commands before cache lookup: sort flags, resolve common aliases, strip redundant whitespace
- Handle equivalent forms: `ls -la` = `ls -al` = `ls --all -l`

**FR-3: Cache lookup in llm_fallback.py**
- Before calling the LLM, check cache for a matching (profile_id, normalized_command) pair
- If match found and command is stateless, return cached response directly
- If no match, call LLM as usual, then store the response in cache

**FR-4: Stateful command detection**
- Maintain a classification of commands as stateless vs. stateful
- Stateless: read-only commands (ls, cat, ps, netstat, uname, etc.)
- Stateful: commands that depend on or modify session state (mkdir, echo >, rm, etc.)
- Only serve cached responses for stateless commands

**FR-5: Optional embedding-based fuzzy matching**
- For cache misses on exact normalized match, optionally check embedding similarity
- Use BAAI/bge-m3 (already in stack) to embed commands
- Similarity threshold configurable (default 0.95 — very conservative)
- Only for stateless commands

**FR-6: Cache population from LLM responses**
- After each LLM call, automatically store the response in cache
- Tag response with session outcome (did attacker continue or terminate after this?)
- When multiple responses exist for the same command, prefer highest-engagement responses

**FR-7: Metrics and monitoring**
- Track cache hit rate per session and over time
- Track LLM calls saved (tokens not spent)
- Report cache growth rate and coverage percentage
- Log which commands still require LLM calls (identifies gaps)

### Non-Functional Requirements

**NFR-1: Response latency**
- Cached responses should be served in <10ms (vs. 1-5s for LLM)
- Embedding similarity lookup should complete in <100ms

**NFR-2: Deception quality**
- Optional minor variation injection for cached responses (timestamp updates, PID randomization)
- Cache should not degrade honeypot believability

**NFR-3: Storage efficiency**
- Typical cache size: ~500-2000 entries per profile
- Estimated storage: <10MB per profile (commands + responses + embeddings)

**NFR-4: Backward compatibility**
- Cache is opt-in via config flag
- When disabled, behavior is identical to current LLM-only fallback

### User Stories

1. **As a researcher**, I want the honeypot to automatically cache LLM responses so that repeated commands are answered instantly without token cost.

2. **As a researcher**, I want to see cache hit rate metrics so I can understand how much LLM cost is being saved over time.

3. **As a researcher**, I want stateful commands (that depend on session history) to always go to the LLM, so that the honeypot remains interactive and realistic.

4. **As a researcher**, I want the cache to persist across experiment runs so that a mature profile benefits from all previous sessions.

### Acceptance Criteria

- [ ] After 50 sessions on the same profile, cache hit rate exceeds 50% for stateless commands
- [ ] After 200 sessions, cache hit rate exceeds 80% for stateless commands
- [ ] Cached responses are served in <10ms
- [ ] Stateful commands (mkdir, echo >, rm) are never served from cache
- [ ] Cache can be disabled with a single config flag
- [ ] Metrics show total LLM tokens saved per session

### Open Questions

1. **Where does the cache live?** Inside the Cowrie Docker container (ephemeral) or mounted as a volume (persistent)? Persistent is needed for the "self-improving" benefit, but adds a volume mount.

2. **How to handle profile reconfiguration?** When the Reconfigurator generates a new profile, the old cache is invalid. Should it be wiped, or can some generic responses carry over (e.g., `whoami` → `root` works on any profile)?

3. **Should cache quality be evaluated?** If a cached response led to the attacker calling `terminate(success=True)` (detected honeypot), that response should probably be evicted or deprioritized. Is this worth implementing?

4. **Embedding model location?** BAAI/bge-m3 is currently used in the Reconfigurator on the host. Running it inside the Cowrie container adds ~500MB to the image. Is the fuzzy matching worth the container bloat, or is normalized exact-match sufficient?

5. **txtcmds promotion?** When a cached response has 100+ hits and high engagement score, should it be automatically "promoted" to a txtcmds file so Cowrie serves it natively without even reaching the fallback handler?

---

**Next step:** Use `/sc:design` to architect the caching layer inside `llm_fallback.py`, the storage format, and the command normalization pipeline.
