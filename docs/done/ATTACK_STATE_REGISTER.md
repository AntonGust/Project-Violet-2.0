# Design: Attack State Register

## Problem

At 200+ iterations across a multi-hop honeynet, the attacker model has no structured memory. It relies entirely on raw conversation history to remember what it did. This causes:

1. **Token cost explosion** — 60K+ context tokens re-sent every call, doubled by followup calls
2. **Context window pressure** — 128K models hit 48% capacity at 200 iters, can overflow with verbose outputs
3. **Attention degradation** — LLMs lose focus on mid-conversation details; credentials found at iteration 5 are effectively "forgotten" by iteration 150
4. **Naive trimming destroys memory** — can't safely trim old messages without losing track of hosts, creds, files

## Prior Art: Cowrie's SessionStateRegister

The defender side already solves this. `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py:156-209` maintains a `SessionStateRegister` with:
- Per-command entries with impact scores (0=read-only → 4=critical)
- Smart pruning: evicts low-impact old entries first
- Formatted for system prompt injection (~200 chars per entry)

The attacker side needs the same pattern, but tracking attacker-specific state.

## Design

### AttackStateRegister class

**File:** `Sangria/attack_state.py` (new)

Tracks five categories of attacker state, updated after every tool call:

```python
class AttackStateRegister:
    """Structured memory for the attacker LLM across long sessions."""

    def __init__(self):
        self.hosts: dict[str, HostEntry] = {}          # ip → host state
        self.credentials: list[CredentialEntry] = []    # all creds found
        self.files_read: list[FileEntry] = []           # files with interesting content
        self.services: list[ServiceEntry] = []          # discovered services
        self.current_host: str = ""                     # where the attacker is now
        self.failed_attempts: list[str] = []            # things that didn't work (avoid repeating)
```

#### Data Structures

```python
@dataclass
class HostEntry:
    ip: str
    hostname: str = ""
    access_level: str = "discovered"   # "discovered" | "user" | "root"
    access_method: str = ""            # "SSH root/123456"
    visited: bool = False

@dataclass
class CredentialEntry:
    credential: str          # "root/dbpass" or "AWS AKIA..."
    source: str              # "/var/www/html/wp-config.php"
    cred_type: str           # "ssh" | "db" | "api_key" | "token" | "other"
    used: bool = False
    used_where: str = ""     # "SSH 172.10.0.4" or "MySQL 172.10.0.3"

@dataclass
class FileEntry:
    path: str                # "/var/www/html/wp-config.php"
    host: str                # "172.10.0.3"
    summary: str             # "DB creds: root/dbpass@localhost"

@dataclass
class ServiceEntry:
    host: str                # "172.10.0.3"
    port: int                # 3306
    service: str             # "MySQL 5.7"
    accessed: bool = False   # whether attacker interacted with it
```

### State Extraction

After each tool call, parse the tool arguments and response to update state.

**Two extraction strategies combined:**

1. **Profile-aware detection (primary):** The register receives the honeypot profile at init. When the attacker reads a file (`cat /var/www/html/wp-config.php`), we check if that path exists in `profile["file_contents"]` and whether it contains credentials (using the same `_CREDENTIAL_KEYWORDS` and `_CREDENTIAL_PATH_PATTERNS` from Cowrie's `llm_fallback.py`). This is **zero false positives** — we know exactly what secrets the profile contains.

2. **Regex fallback:** For credentials found via commands we can't profile-match (e.g., output of `env`, `history`, or commands on lateral-movement hosts), fall back to regex patterns.

**Command matching:** Parse the first token (the binary name) to avoid false positives. `"ssh" in command` matches `cat /etc/ssh/sshd_config` — instead, split on whitespace and check `tokens[0]`.

**MITRE tracking:** The tool call already includes `tactic_used` and `technique_used` fields. These are free structured data — track them in the state register for post-session analysis without any parsing cost.

```python
def __init__(self, profile: dict | None = None):
    # ... existing fields ...
    self._profile = profile or {}
    self._file_contents = self._profile.get("file_contents", {})
    self._credential_paths = self._precompute_credential_paths()
    self._seen_credentials: set[tuple[str, str]] = set()  # (cred, source) dedup

def update_from_tool_call(self, fn_name: str, fn_args: dict, response: str):
    """Extract state changes from a tool call and its response."""

    if fn_name == "terminal_input":
        command = fn_args.get("input", "")
        tactic = fn_args.get("tactic_used", "")
        technique = fn_args.get("technique_used", "")
        self._parse_command(command, response, tactic, technique)

    elif fn_name == "terminate":
        pass  # no state change

def _get_command_binary(self, command: str) -> str:
    """Extract the binary name from a command string."""
    tokens = command.strip().split()
    if not tokens:
        return ""
    # Skip sudo/env prefixes
    while tokens and tokens[0] in ("sudo", "env"):
        tokens = tokens[1:]
    return tokens[0] if tokens else ""

def _parse_command(self, command: str, response: str, tactic: str, technique: str):
    """Parse command + response for state-relevant information."""
    binary = self._get_command_binary(command)

    # SSH connection attempts
    if binary == "ssh":
        self._parse_ssh(command, response)

    # File reads — profile-aware credential detection
    if binary in ("cat", "head", "tail", "less", "more"):
        self._parse_file_read(command, response)

    # Network discovery
    if binary in ("nmap", "netstat", "ss"):
        self._parse_network(command, response)

    # Database access
    if binary in ("mysql", "psql"):
        self._parse_db_access(command, response)

    # Host change tracking (parse prompt pattern from response)
    self._update_current_host(response)

def _parse_file_read(self, command: str, response: str):
    """Profile-aware file read tracking.

    Check if the file path exists in the profile's file_contents.
    If it's a known credential file, mark those credentials as discovered.
    Falls back to regex for unknown files.
    """
    # Extract file path from command (e.g., "cat /var/www/html/wp-config.php")
    tokens = command.strip().split()
    file_path = tokens[-1] if len(tokens) > 1 else ""

    if file_path in self._credential_paths:
        # Profile-aware: we know exactly what's in this file
        self._extract_credentials_from_profile(file_path)
    elif response:
        # Regex fallback for files not in profile
        self._extract_credentials_regex(file_path, response)

def _add_credential(self, credential: str, source: str, cred_type: str):
    """Add credential with deduplication."""
    key = (credential, source)
    if key in self._seen_credentials:
        return
    self._seen_credentials.add(key)
    self.credentials.append(CredentialEntry(
        credential=credential, source=source, cred_type=cred_type
    ))
```

### Credential Detection Heuristics

```python
# Patterns that indicate credentials in file output
_CRED_PATTERNS = [
    (r"password\s*[=:]\s*['\"]?(\S+)", "password"),
    (r"AKIA[A-Z0-9]{16}", "aws_key"),
    (r"(?:api[_-]?key|token|secret)\s*[=:]\s*['\"]?(\S+)", "api_key"),
    (r"mysql://(\S+):(\S+)@", "db_connection"),
    (r"postgres://(\S+):(\S+)@", "db_connection"),
    (r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----", "ssh_key"),
]
```

### Prompt Injection Format

The state register gets injected into the system prompt, replacing raw history for older iterations:

```
ATTACK STATE (auto-tracked):
═══════════════════════════════════════

HOSTS:
  172.10.0.3 (wp-prod-01) — root access via SSH [root/123456] ✓
  172.10.0.4 (db-replica-01) — root access via SSH [root/dbpass] ✓
  172.10.0.5 (backup-srv) — discovered, not yet accessed

CREDENTIALS:
  [USED]   root/123456 → SSH 172.10.0.3 ✓
  [USED]   root/dbpass → SSH 172.10.0.4 ✓ (source: wp-config.php)
  [UNUSED] deploy/d3pl0y! (source: /var/mail/deploy)
  [UNUSED] AWS AKIA... (source: /home/deploy/.env)
  [UNUSED] jenkins:eyJh... (source: .jenkins_api_token)

FILES WITH SECRETS:
  172.10.0.3:/var/www/html/wp-config.php — DB creds: root/dbpass@localhost
  172.10.0.3:/home/deploy/.env — AWS access key + secret
  172.10.0.3:/home/deploy/.jenkins_api_token — Jenkins API token

SERVICES:
  172.10.0.3:3306 MySQL 5.7 — NOT YET ACCESSED ← try this!
  172.10.0.3:80 Apache 2.4 — accessed

FAILED ATTEMPTS:
  ssh deploy@172.10.0.5 — Connection refused

CURRENT POSITION: root@db-replica-01 (172.10.0.4)
```

**Token cost:** ~300-500 tokens regardless of session depth (vs ~60K raw history at iteration 200).

### Integration with Message History Trimming

The state register enables safe trimming. The combined strategy:

```
┌─────────────────────────────────────────┐
│  SYSTEM PROMPT (base + objectives)      │  ~800 tokens (static)
├─────────────────────────────────────────┤
│  ATTACK STATE REGISTER                  │  ~300-500 tokens (grows slowly)
├─────────────────────────────────────────┤
│  RECENT HISTORY (last 5-10 iterations)  │  ~1,500-3,000 tokens (sliding window)
├─────────────────────────────────────────┤
│  CURRENT COMMAND/RESPONSE               │  variable
└─────────────────────────────────────────┘

Total: ~3,000-5,000 tokens regardless of session depth
vs current: ~60,000 tokens at iteration 200
```

Old messages beyond the window are discarded — their essential information lives in the state register.

### Integration Points

**File:** `Sangria/sangria.py`

```python
from Sangria.attack_state import AttackStateRegister

def run_single_attack(messages, max_session_length, ...):
    state = AttackStateRegister(profile=honeypot_config)
    base_system_prompt = messages[0]["content"]  # preserve original

    for i in range(max_session_length):
        # Rebuild system prompt with current state (don't mutate original)
        messages[0] = {
            "role": "system",
            "content": base_system_prompt + "\n\n" + state.to_prompt_string()
        }

        # ... existing decision call ...

        for tool_use in tool_calls:
            fn_args = json.loads(tool_use.function.arguments)
            result = handle_tool_call(fn_name, fn_args, ssh)

            # Update state register
            state.update_from_tool_call(fn_name, fn_args, str(result['content']))

        # Trim old messages if window exceeded (keep system prompt + recent)
        if len(messages) > history_window_size:
            messages = [messages[0]] + messages[-history_window_size:]
```

**Note:** The system prompt dict is replaced (not mutated in place) each iteration. The file log captures the state at log-time. `base_system_prompt` is preserved so the state register section is always cleanly rebuilt from current state.

**File:** `Sangria/attacker_prompt.py` — no change. The state register is appended to the system prompt dynamically in sangria.py, not baked into the static prompt.

### Token Savings with State Register

| Session depth | Current (raw history) | With state register + window=10 | Savings |
|---------------|----------------------|--------------------------------|---------|
| 10 iterations | ~4,200 tokens/call | ~3,500 tokens/call | 17% |
| 50 iterations | ~16,200 tokens/call | ~4,000 tokens/call | 75% |
| 100 iterations | ~31,200 tokens/call | ~4,500 tokens/call | 86% |
| 200 iterations | ~61,200 tokens/call | ~5,000 tokens/call | 92% |

### Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Credential regex misses a format | Primary strategy is profile-aware (zero false positives for known files). Regex is only a fallback for lateral-movement hosts where we don't have the profile. |
| Duplicate credentials from re-reading files | Dedup by `(credential, source)` tuple in `_seen_credentials` set. |
| State register grows too large | Cap at ~50 entries per category. Prune oldest/lowest-impact (same as Cowrie's approach). |
| Model ignores state register | Place it immediately after the base prompt, before objectives. Mark UNUSED credentials prominently. |
| Parsing errors corrupt state | State extraction is additive-only. Bad parses add noise but don't remove existing state. |

### Logging

The state register should be saved to the session log at the end of each session for analysis:

```python
# After session ends
save_json_to_file(state.to_dict(), config_path / "attack_state.json")
```

This also enables post-session analysis: "how many credentials were found vs used?" becomes a simple JSON query.

## Implementation Order — ✅ ALL COMPLETE

1. ~~**AttackStateRegister class** with host/credential/file tracking~~ ✅ `Sangria/attack_state.py`
2. ~~**State extraction** from tool call args + responses (regex-based)~~ ✅ Profile-aware + regex fallback
3. ~~**System prompt injection** in sangria.py~~ ✅ Rebuilt each iteration when `history_window > 0`
4. ~~**Message window trimming** (safe now that state register preserves context)~~ ✅ `config.history_window = 10`
5. ~~**Logging** — save final state to session JSON~~ ✅ `attack_state_N.json`

## Relationship to Other Plans

- **TOKEN_SAVINGS.md** — ✅ Done. All four opportunities implemented.
- **MYSQL_AND_PROMPT_DESIGN.md** — The model-specific addenda for Llama ("NEVER SSH to the same host twice") becomes less critical once the state register shows visited hosts explicitly. But both should be implemented — belt and suspenders.
