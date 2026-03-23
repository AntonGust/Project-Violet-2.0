# LLM Fallback System: How It Works and How It Differs from the Naive Approach

## The Problem

When an SSH honeypot receives a command it doesn't have a native handler for (e.g., `aws s3 ls`, `docker inspect`, `dpkg -l`), it needs to produce a realistic response. The simplest approach — which the Go-based Beelzebub component still uses — is to send the **entire session history** to an LLM and ask "what would this command output?" This is what we call the **naive/legacy approach**.

## The Naive Approach (Beelzebub / Go)

In `Blue_Lagoon/plugins/llm-integration.go:147-209`, every command is handled by:

1. A **static system prompt** (~200 tokens): *"You will act as an Ubuntu Linux terminal..."*
2. A **hardcoded example pair** (`pwd` → `/home/user`)
3. The **entire conversation history** — every prior command and response, unbounded
4. The current command

**No profile awareness.** No filesystem context. No command-specific context selection. The LLM must hallucinate package lists, services, file contents, and credentials purely from its training data — producing inconsistent and detectable responses.

**Token growth is linear and unbounded**: each new command appends to the history, so by command 50 in a session, the prompt includes all 49 prior command-response pairs.

## The Prequery Approach (Cowrie / Python)

The current system (`llm_fallback.py` + `prequery.py`) uses a fundamentally different architecture with three key innovations:

### 1. Command-Aware Context Injection (prequery.py)

Instead of dumping everything, the system **parses each command before sending it** and injects only the context the LLM needs to answer that specific command.

The pipeline (`prequery.py:124-151`):
1. Split compound commands on `|`, `&&`, `||`, `;`
2. Strip wrapper prefixes (`sudo`, `nohup`, `env`, etc.)
3. Match the base command against **117 command-family mappings** to context keys
4. Extract filesystem paths from arguments (3-tier: positional args, flag-value pairs, regex scan)
5. Resolve each path against live filesystem, then profile JSON, then parent-path walking

For example:
- `dpkg -l` injects `packages` context (list of installed packages from profile)
- `docker ps` injects `container_context` (services, containers from docker-compose files in profile)
- `cat /etc/passwd` injects `path:/etc/passwd` context (file metadata or preview from profile)
- `aws s3 ls` injects `cloud_context` (credentials, buckets, region extracted from profile files)

### 2. Budget-Aware Assembly (prequery.py:250-301)

All extracted context is assembled into a text block capped at **3,000 characters** (`MAX_CONTEXT_CHARS`). Path-specific context is prioritized first, then remaining context types fill the budget. If context exceeds the budget, it is truncated.

### 3. State Register Instead of Full History (llm_fallback.py:156-210)

Instead of replaying the entire session, a **SessionStateRegister** maintains a compact summary of what happened:

```
STATE REGISTER (accumulated changes this session):
- [0] whoami: root
- [2] apt install nginx: Reading package lists... Done
- [0] id: uid=0(root) gid=0(root) groups=0(root)
```

Each entry stores: command, response summary (truncated to 200 chars), and impact score (0-4). When the register exceeds 50 entries, it prunes low-impact old entries while preserving high-impact ones (privilege changes, file modifications).

The conversation history is also maintained but **windowed to the last 20 command-response pairs** (`max_history`, `llm_fallback.py:265-266`), and this is separate from the state register.

## What Gets Sent to the LLM

The `build_prompt` method (`llm_fallback.py:484-575`) constructs the final message list:

```
+----------------------------------------------+
| SYSTEM MESSAGE                               |
|  +-- Base system prompt (~300 tokens)        |
|  |   (hostname, OS, services, rules)         |
|  +-- State register (~100-300 tokens)        |
|  |   (compact summary of session changes)    |
|  +-- Prequery context (~200-800 tokens)      |
|      (ONLY what this command needs)          |
+----------------------------------------------+
| HISTORY (last 20 pairs, ~200-500 tokens)     |
|  user: whoami                                |
|  assistant: root                             |
|  user: ls -la /var/www                       |
|  assistant: total 24\ndrwxr-xr-x ...        |
+----------------------------------------------+
| CURRENT COMMAND                              |
|  user: dpkg -l | grep mysql                  |
+----------------------------------------------+
```

## Token Savings Estimate

| Component | Naive (Beelzebub) | Prequery (Cowrie) |
|---|---|---|
| System prompt | ~60 tokens (static) | ~300 tokens (profile-aware) |
| Context injection | 0 (none) | 200-800 tokens (command-specific) |
| Session history (cmd 10) | ~1,500 tokens (all 10 pairs) | ~500 tokens (10 pairs, same) |
| Session history (cmd 30) | ~4,500 tokens (all 30 pairs) | ~1,000 tokens (last 20 pairs) |
| Session history (cmd 50) | ~7,500 tokens (all 50 pairs) | ~1,000 tokens (capped at 20) |
| Session history (cmd 100) | ~15,000 tokens (all 100 pairs) | ~1,000 tokens (capped at 20) |
| State register | 0 | 100-300 tokens |
| **Total at cmd 10** | **~1,560** | **~1,600-2,100** |
| **Total at cmd 30** | **~4,560** | **~1,600-2,100** |
| **Total at cmd 50** | **~7,560** | **~1,600-2,100** |
| **Total at cmd 100** | **~15,060** | **~1,600-2,100** |

**Key insight**: The prequery system has slightly higher overhead at the start of a session (profile-aware prompt + context injection is approximately 500 extra tokens vs naive), but it **stays constant** while the naive approach grows linearly. By command 50, the prequery system uses **~73% fewer tokens**. By command 100, it uses **~86% fewer tokens**.

## Additional Savings Mechanisms

- **Response caching** (`llm_fallback.py:289-349`): Identical commands (normalized) return cached responses with zero API calls. Cache is profile-scoped (invalidated on profile change via SHA-256 hash).
- **Native command handlers**: 50+ commands (`ps`, `ls`, `cat`, `grep`, `find`, `systemctl`, `docker`, `mysql`, etc.) are handled natively without any LLM call at all. The LLM only receives commands the native layer cannot handle.
- **Fallback directory tree**: If prequery finds no relevant context for a command, only then does it inject the full directory tree as a last resort (`llm_fallback.py:559-561`).

## Context Window Impact

| Metric | Naive | Prequery |
|---|---|---|
| Context window needed (100 cmds) | ~16K tokens | ~2.5K tokens |
| Max context growth | Unbounded (linear) | Bounded (~2.5K ceiling) |
| Fits in 4K context window | Only first ~25 cmds | All commands |
| Fits in 8K context window | Only first ~50 cmds | All commands |
| Profile consistency | None (hallucinated) | Full (profile-injected) |

The bounded context means cheaper models with smaller context windows (e.g., GPT-4.1-Mini with 4K output) can be used effectively for the honeypot, whereas the naive approach would require progressively larger (and more expensive) models as sessions lengthen.

## The Quality Tradeoff

The prequery system does not just save tokens — it **improves response quality**:

- **Consistency**: Responses are grounded in the actual profile (packages, services, users, file contents) rather than hallucinated.
- **Credential accuracy**: DB credentials extracted from profile files (`extract_db_credentials`) are injected into context so the LLM accepts the correct passwords.
- **Real DB integration**: When a database proxy is available, actual SQL query results are injected (`llm_fallback.py:532-542`).
- **Install tracking**: `apt install nginx` updates a package overlay so subsequent `dpkg -l` reflects the installation (`llm_fallback.py:702-717`).
