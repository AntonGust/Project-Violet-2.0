# SSH "Channel closed" on First Hop Connection

## Status: Done

## Issue Description
When the SSH proxy connects from one Cowrie hop to another, the **first connection always fails** with `ssh: failed to open shell: Channel closed.` The second connection succeeds. This affects ALL hops, not just hop 3.

## Evidence

| Run | Hop 1→2 (first) | Hop 1→2 (retry) | Hop 2→3 |
|-----|------------------|------------------|---------|
| 2026-03-28 | Login → close 0.1s (FAIL) | Login → shell (OK) | Login → close 0.0s (FAIL, no retry) |
| 2026-03-25 | Login → close 0.0s (FAIL) | Login → shell (OK) | (not attempted) |

The server-side cowrie.json confirms: login succeeds, then session closes immediately with NO pty/shell events logged.

## Root Cause Analysis

The failure chain is:

1. **`SSHProxySession.connect()`** calls `self._client.invoke_shell(term="xterm", width=80, height=24)`
2. paramiko internally calls `Channel.get_pty()` → sends SSH `CHANNEL_REQUEST (pty-req)` with `want_reply=True`
3. Cowrie's `CowrieSSHConnection.ssh_CHANNEL_REQUEST()` dispatches to `HoneyPotSSHSession.request_pty_req()`
4. `request_pty_req()` creates `ISession(self.avatar)` → instantiates `SSHSessionForCowrieUser`
5. **On FIRST connection**: `SSHSessionForCowrieUser.__init__()` calls `self.server.initFileSystem()` which does the heavy pickle load + honeyfs walk. **Something in this first-time initialization causes the pty request to fail** (returns `False` or raises an exception caught by the bare `except:` in Twisted's `request_pty_req`)
6. The server sends `MSG_CHANNEL_FAILURE` for the pty-req
7. paramiko's `get_pty()._wait()` detects the failure → closes the channel → raises `SSHException("Channel closed.")`
8. `ssh_proxy.py` catches this and writes `ssh: failed to open shell: Channel closed.`

**On SECOND connection**: `CowrieServer.fs` is already initialized (check `if self.fs is not None: return`), so `initFileSystem` returns immediately. The pty-req succeeds and the shell opens.

### Why hop 3 never recovered
The attacker LLM only retried hop 2 because it was earlier in the session and the model was still exploring. By the time it tried hop 3, it had already started suspecting a honeypot and didn't retry after the failure.

## Key Files

| File | Role |
|------|------|
| `Cowrie/cowrie-src/src/cowrie/commands/ssh_proxy.py` | SSHProxySession — `invoke_shell()` fails here (line 88-101) |
| `Cowrie/cowrie-src/src/cowrie/commands/ssh.py` | SSH command handler, creates proxy, reports error (line 216-219) |
| `Cowrie/cowrie-src/src/cowrie/ssh/connection.py` | `CowrieSSHConnection.ssh_CHANNEL_REQUEST()` — shell request auto-succeeds, pty-req does not (line 49-68) |
| `Cowrie/cowrie-src/src/cowrie/shell/session.py` | `SSHSessionForCowrieUser.__init__()` — calls `initFileSystem()` (line 57) |
| `Cowrie/cowrie-src/src/cowrie/shell/server.py` | `CowrieServer.initFileSystem()` — heavy pickle load + honeyfs walk (line 81-96) |
| `Cowrie/cowrie-src/src/cowrie/shell/fs.py` | `HoneyPotFilesystem.__init__()` — pickle.load + init_honeyfs (line 109-158) |
| `Cowrie/cowrie-src/src/cowrie/ssh/session.py` | `HoneyPotSSHSession` — channel/session lifecycle (closeReceived override) |
| `Cowrie/cowrie-src/src/cowrie/ssh/channel.py` | `CowrieSSHChannel` — channel lifecycle (closeReceived override) |
| `docker-compose.honeynet.yml` | Network topology — all hops on shared `net_attack` 172.10.0.0/24 |

## Proposed Solutions (ranked by impact)

### Solution 1: Retry in SSHProxySession (quick fix, high confidence)
Add a single retry with a brief delay in `SSHProxySession.connect()` when `invoke_shell()` fails with "Channel closed":

```python
# In ssh_proxy.py connect(), replace the invoke_shell try block:
for attempt in range(2):
    try:
        self._channel = self._client.invoke_shell(
            term="xterm", width=80, height=24,
        )
        self._channel.settimeout(0.1)
        break
    except Exception as e:
        if attempt == 0 and "Channel closed" in str(e):
            log.msg(f"SSH proxy shell failed on first attempt, retrying: {e}")
            self._cleanup()
            time.sleep(0.5)
            # Re-establish connection
            try:
                self._client = paramiko.SSHClient()
                self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self._client.connect(
                    hostname=self.host, port=self.port,
                    username=self.username, password=self.password,
                    timeout=10, look_for_keys=False, allow_agent=False,
                )
            except Exception:
                self._cleanup()
                return self.CONNECT_UNREACHABLE
            continue
        reactor.callFromThread(
            self.command.write, f"ssh: failed to open shell: {e}\n"
        )
        log.msg(f"SSH proxy shell request failed: {e}")
        self._cleanup()
        return self.CONNECT_UNREACHABLE
```

**Risk:** Low. Only retries on the specific "Channel closed" error.

### Solution 2: Pre-initialize filesystem at server startup (root cause fix)
Move `initFileSystem` from `SSHSessionForCowrieUser.__init__()` to `CowrieServer.__init__()` so the heavy pickle load happens once at startup, not during the first SSH session:

```python
# In shell/server.py CowrieServer.__init__():
def __init__(self, realm):
    ...
    # Pre-initialize filesystem so first session doesn't pay init cost
    self.initFileSystem("/root")  # default home
```

**Risk:** Low-medium. Needs verification that `initFileSystem` can run without a specific home dir, or that `/root` is always valid.

### Solution 3: Add debug logging (investigation aid)
Add exception logging to `SSHSessionForCowrieUser.__init__()` and `request_pty_req` to capture the exact failure on next run:

```python
# In shell/session.py SSHSessionForCowrieUser.__init__():
try:
    self.server.initFileSystem(self.avatar.home)
except Exception as e:
    log.msg(f"initFileSystem failed: {e}")
    raise
```

**Risk:** None.

## Recommendation
**Implement Solution 1 (retry) + Solution 3 (logging) first.** Solution 1 fixes the user-facing issue immediately. Solution 3 captures root cause data for a future proper fix. Solution 2 can be attempted once we confirm the exact failure via Solution 3's logging.

## Related
- `docs/known-problems/cowrie-fake-ssh-loopback.md` — previous SSH loopback issue (fixed 2026-03-25b)
- `docs/known-problems/urgent-fixes-wordpress-hardening.md` — issue #1 (this doc supersedes that entry)
