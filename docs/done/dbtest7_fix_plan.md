# Fix Plan: 4 Honeypot Issues from dbtest7 Logs

## Context

dbtest7 attack_1 ran 109 commands with a deep, realistic attack chain (privesc → credential extraction → lateral movement). The previous round of fixes (sudo escalation, SSH flow, find fallback, SCP outbound, MITRE filtering) all worked. However, 4 new issues emerged, with **file persistence across sessions** being the dominant problem (~30 commands wasted, 27% of session).

---

## Fix 1: File Persistence Across SSH Sessions (CRITICAL — ~30 commands wasted)

**Problem:** Files written inside the honeypot (via `echo '...' > file`) disappear when the attacker exits SSH and reconnects. The attacker wrote hashes to `/root/wp_hashes.txt` three separate times across sessions, each time finding the file gone on re-entry.

**Root cause:** `realm.py:50` creates a **new `CowrieServer`** for every `requestAvatar()` call. Each `CowrieServer` creates a fresh `HoneyPotFilesystem` from the pickle file in `server.py:85`. The in-memory virtual FS (including all `mkfile`/redirect-created files) is discarded when the session ends.

**Architecture note:** The `CowrieServer` docstring already says: *"This class represents a 'virtual server' that can be shared between multiple Cowrie connections."* The per-session isolation was a design choice, not an architectural constraint.

### Changes

#### 1a. Cache shared server in realm
**File:** `Cowrie/cowrie-src/src/cowrie/shell/realm.py`

- Add a `_server` instance variable to `HoneyPotRealm.__init__()`, initialized to `None`
- In `requestAvatar()`, reuse `self._server` if it exists; create once on first call
- This means all SSH sessions share the same `CowrieServer` → same `HoneyPotFilesystem`

```python
def __init__(self) -> None:
    self._server = None

def requestAvatar(self, avatarId, _mind, *interfaces):
    if self._server is None:
        self._server = shellserver.CowrieServer(self)
    serv = self._server
    ...
```

#### 1b. Make `initFileSystem` idempotent
**File:** `Cowrie/cowrie-src/src/cowrie/shell/server.py`

- In `initFileSystem()`, skip if `self.fs` is already initialized
- This prevents re-loading the pickle on the second SSH session

```python
def initFileSystem(self, home: str) -> None:
    if self.fs is not None:
        return
    self.fs = fs.HoneyPotFilesystem(self.arch, home)
    ...
```

#### 1c. Apply same change to LLM realm
**File:** `Cowrie/cowrie-src/src/cowrie/llm/realm.py`

- Same pattern: cache `_server` in `HoneyPotRealm`, reuse across avatar requests

---

## Fix 2: Multiline Shell Input (Heredocs + Quote Continuation) (~6 commands wasted)

**Problem:** `cat << EOF > file` and multiline `echo '...'` fail with "syntax error: unexpected end of file". Real bash buffers these and shows `> ` continuation prompt.

**Root cause:** `HoneyPotShell.lineReceived()` processes exactly one line at a time. `shlex` raises `ValueError` on unclosed quotes → error message + discard. There is zero heredoc/continuation infrastructure.

### Changes

**File:** `Cowrie/cowrie-src/src/cowrie/shell/honeypot.py`

#### 2a. Add line continuation buffer to `HoneyPotShell.__init__()`

Add instance variables:
- `self._line_buffer: str = ""` — accumulates partial input
- `self._heredoc_delim: str | None = None` — heredoc delimiter when in heredoc mode
- `self._heredoc_lines: list[str] = []` — accumulated heredoc body lines
- `self._heredoc_redirect: str | None = None` — file target for heredoc output

#### 2b. Quote continuation in `lineReceived()`

When `shlex` raises `ValueError` (unclosed quote):
1. Instead of showing error, save the line in `self._line_buffer`
2. Show `> ` continuation prompt (write `b"> "` to terminal, set secondary prompt)
3. On next `lineReceived()`, prepend buffer: `line = self._line_buffer + "\n" + line`
4. Try parsing again. If still unclosed, keep buffering. If success, process normally.

#### 2c. Heredoc detection and buffering

After successful shlex tokenization, scan tokens for `<<`:
1. If `<<` found, extract the delimiter (next token, strip quotes)
2. Extract any redirect target from the tokens (the `> file` part before `<<`)
3. Store in `self._heredoc_delim` and `self._heredoc_redirect`
4. Show `> ` continuation prompt
5. On subsequent `lineReceived()` calls: if `self._heredoc_delim` is set:
   - If line matches delimiter: assemble heredoc body, feed to command's stdin via redirect
   - Else: append line to `self._heredoc_lines`, show `> ` prompt again

#### 2d. Heredoc execution

When delimiter is matched:
- Join `_heredoc_lines` with `\n`
- If there was a redirect target (`> file`), create the file and write content
- If there was a command (`cat << EOF`), feed content as stdin to that command
- Reset all heredoc state variables

---

## Fix 3: SCP Pull Mode (Kali → Honeypot Download) (~4 commands wasted)

**Problem:** `scp -P 2222 deploy@honeypot:/file /local/` from Kali times out. The honeypot receives `scp -f /file` via exec channel but doesn't handle `-f` (from/send) mode.

**Root cause:** `scp.py:start()` only handles `-t` (to/receive) mode and the outbound simulation we added. When `-f` is in the args, it falls through to the default path that writes 10 `\x00` bytes and waits for data — but in `-f` mode, the *server* should be *sending* data.

### Changes

**File:** `Cowrie/cowrie-src/src/cowrie/commands/scp.py`

In `start()`, after getopt parsing, detect `-f` in optlist:

1. Extract the requested file path from args
2. Resolve it in the virtual filesystem (`self.fs.resolve_path()`)
3. If file exists:
   - Read content via `self.fs.file_contents()` or the `A_REALFILE` backing
   - Send SCP protocol header: `C0644 <size> <filename>\n`
   - Send file content bytes
   - Send `\x00` (success marker)
   - Exit
4. If file doesn't exist:
   - Send `\x01scp: <path>: No such file or directory\n`
   - Exit

```python
for opt in optlist:
    if opt[0] == "-f":
        self._handle_pull(args)
        return
```

---

## Fix 4: Sudo + Pipe Filtering (LOW — minor confusion)

**Problem:** `sudo netstat -tulnp | grep ':80\|:443'` returns full unfiltered netstat output instead of just matching lines.

**Root cause:** The pipe `|` splits the command into two segments: `sudo netstat -tulnp` and `grep ':80\|:443'`. The `sudo` command runs `netstat` via `PipeProtocol.insert_command()`. However, `sudo.py:182-185` creates a **nested** PipeProtocol for the inner command but doesn't properly chain it to the outer pipe's `next_command`. The `netstat` output goes to the terminal directly instead of flowing through `grep`.

### Changes

**File:** `Cowrie/cowrie-src/src/cowrie/commands/sudo.py`

In the `parsed_arguments` block where `PipeProtocol` is created for the sudoed command:
- Instead of creating a standalone PipeProtocol and inserting it, pass the existing pipe chain's `next_command` (which is `grep`) to the inner PipeProtocol so output flows correctly

Specifically, when `sudo` runs `netstat` and there's a pipe after sudo:
- The outer PipeProtocol for `sudo` has `self.protocol.pp.next_command` pointing to `grep`'s PipeProtocol
- Pass that `next_command` to the inner command's PipeProtocol instead of `None`

```python
# Current (broken for pipes):
command = PipeProtocol(self.protocol, cmdclass, parsed_arguments[1:], None, None)

# Fixed: propagate the pipe chain
outer_pp = self.protocol.pp
command = PipeProtocol(
    self.protocol, cmdclass, parsed_arguments[1:],
    None, outer_pp.next_command if outer_pp else None
)
```

---

## Files Modified (6 total)

| File | Fix | Change |
|------|-----|--------|
| `Cowrie/.../shell/realm.py` | 1a | Cache shared CowrieServer |
| `Cowrie/.../shell/server.py` | 1b | Make `initFileSystem` idempotent |
| `Cowrie/.../llm/realm.py` | 1c | Same shared server pattern |
| `Cowrie/.../shell/honeypot.py` | 2 | Heredoc + quote continuation buffering |
| `Cowrie/.../commands/scp.py` | 3 | Handle `-f` (pull) mode |
| `Cowrie/.../commands/sudo.py` | 4 | Propagate pipe chain through sudo |

## Verification

1. **Rebuild Cowrie Docker image** — all changes are inside `Cowrie/cowrie-src/`
2. **File persistence test**: SSH in, `echo 'test' > /tmp/testfile`, exit, SSH in again, `cat /tmp/testfile` should return "test"
3. **Heredoc test**: `cat << EOF > /tmp/multi\nline1\nline2\nEOF` should create file with two lines
4. **Quote continuation test**: Type `echo 'hello`, press Enter, see `> ` prompt, type `world' > /tmp/qtest`, file should contain "hello\nworld"
5. **SCP pull test**: From Kali, `scp -P 2222 deploy@honeypot:/etc/passwd /tmp/` should transfer the file
6. **Sudo pipe test**: `sudo netstat -tulnp | grep ':80'` should only show port 80 lines
7. **Run existing tests**: `pytest Tests/` to ensure no regressions

---

## Diagnostic Summary from dbtest7 attack_1

### What Worked (from previous fixes)
- **Sudo escalation**: `sudo -i` → `root@wp-prod-01:~#`, uid=0 ✅
- **SSH flow**: Direct password prompt, no timeout ✅
- **LLM content**: MySQL, .env, backup scripts, SSH keys, WordPress DB all rich and realistic ✅
- **Netstat/ss profile data**: Realistic service listings ✅

### What Failed
| Issue | Commands Wasted | % of Session |
|-------|----------------|--------------|
| File persistence across sessions | ~30 | 27% |
| Multiline echo/heredoc | ~6 | 5% |
| SCP pull from Kali | ~4 | 4% |
| Sudo + pipe filtering | ~2 | 2% |

### Session ended with: `discovered honeypot: yes` (success: True)
The attacker eventually detected the honeypot, likely due to files disappearing between sessions.
