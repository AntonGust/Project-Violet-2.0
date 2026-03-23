# SCP Fix: Two-Direction Simulation

## Root Cause

In `Cowrie/cowrie-src/src/cowrie/commands/scp.py` line 85, outbound detection only checks `args[-1]`:

```python
if args and re.match(r"^(?:\S+@)?[\w.\-]+:.+$", args[-1]):
```

When the attacker runs `scp deploy@10.0.1.20:/path /tmp/`, the args are:
- `args[0]` = `deploy@10.0.1.20:/var/backups/wp/...` (remote source)
- `args[-1]` = `/tmp/` (local destination)

The regex only matches `args[-1]`, so the remote pattern in `args[0]` is missed. The handler falls through to **inbound SCP protocol mode**, which writes `\x00` bytes and waits for binary SCP data that never arrives. Cowrie hangs, terminal_io's timeout kills the SSH connection, and the attacker bails.

## Design: Two-Direction SCP Simulation

### Direction Detection

Scan ALL args for the remote pattern, not just the last:

| Pattern | Direction | Example |
|---|---|---|
| Remote in `args[-1]` | **Push** (local → remote) | `scp /tmp/file user@host:/path` |
| Remote in `args[0:-1]` | **Pull** (remote → local) | `scp user@host:/path /tmp/` |

### Push (already works)

Keep existing `_handle_outbound` — reads local file from honeyfs, prints progress bar.

### Pull (new)

New `_handle_pull_remote` method:

1. Parse the remote arg to extract `user`, `host`, `path`
2. Check if `host` exists in the virtual `/etc/hosts` (profile data) or is a known honeynet hop
3. **If the remote file has content** (see Remote File Content below) → simulate successful download with progress bar, create the file in VFS with real content in honeyfs so `cat` works
4. **If the host is in `/etc/hosts` but no content available** → simulate success with progress bar, create a stub file in VFS (size only, no content)
5. **If the host is unknown** → simulate `ssh: connect to host X port 22: Connection refused` (fast fail, no hang)
6. **If honeynet mode and target is a known hop** → future enhancement: proxy SCP via paramiko SFTP

### Simulated Pull Output

Success:
```
deploy@10.0.1.20's password:
db_backup_20260315.sql.gz     100%  2.4MB   1.2MB/s   00:02
```

Connection failure:
```
ssh: connect to host 10.0.1.20 port 22: Connection refused
```

## Remote File Content via Profile Schema

### Problem

The pickle/honeyfs only has files for the **local** honeypot. When the attacker SCPs a file from a remote host (e.g. `10.0.1.20`), there is no content to serve. Without real content, the attacker would notice the file is empty or missing after download.

### Solution: Expand the Profile Schema

Add a `remote_files` section to the profile JSON that defines files available on the fake hosts referenced in `/etc/hosts` and SSH config. This is deterministic, requires no LLM at runtime, and the content is baked into honeyfs at deploy time.

#### Schema Addition

```json
{
  "remote_files": {
    "10.0.1.20": {
      "/var/backups/wp/db_backup_20260315.sql.gz": {
        "content_type": "binary",
        "size": 2457600,
        "description": "gzipped MySQL dump of wordpress_prod"
      },
      "/var/backups/wp/db_backup_20260314.sql.gz": {
        "content_type": "binary",
        "size": 2389504
      }
    },
    "10.0.1.50": {
      "/var/lib/jenkins/credentials.xml": {
        "content_type": "text",
        "content": "<credentials>...</credentials>"
      }
    }
  }
}
```

Fields:
- **`content_type`**: `"text"` (stored as-is in honeyfs) or `"binary"` (generated as random bytes of given size, or a realistic placeholder)
- **`content`**: Actual file content for text files. Provided by the profile generator.
- **`size`**: File size in bytes. Used for VFS entry and progress bar display.
- **`description`**: Optional hint for the profile generator about what this file represents.

#### Profile Generator Changes

`Reconfigurator/new_config_pipeline.py` already analyzes scripts for lateral movement targets. Extend it to:

1. **Scan scripts for SCP/rsync references** — extract `user@host:path` patterns from `file_contents`
2. **Generate plausible content** — for each referenced remote file:
   - Text files (configs, credentials): generate content consistent with the profile theme
   - Binary files (backups, archives): note the size, content generated at deploy time as random bytes or minimal valid archive
3. **Add to `remote_files`** in the profile JSON

#### Profile Converter Changes

`Reconfigurator/profile_converter.py` deploys profiles to Cowrie artifacts. Extend it to:

1. **Read `remote_files`** from the profile
2. **Write text content to honeyfs** under a namespaced path: `honeyfs/_remote/<host>/<path>`
3. **Generate binary stubs** for binary files (e.g. minimal gzip header + random bytes)
4. **Build a lookup index** saved as `etc/remote_files.json` inside the Cowrie config, so the SCP handler can quickly check if a remote file exists and where its content lives

#### SCP Handler Changes

`_handle_pull_remote` loads the remote files index and:

1. Looks up `host + path` in the index
2. If found: reads content from `honeyfs/_remote/<host>/<path>`, creates file in VFS at the local destination, shows realistic progress bar
3. If not found but host is known: creates stub file (size only), shows progress bar
4. If host unknown: connection refused

### How It Fits Together

```
Profile Generator (LLM)
    ↓ generates remote_files entries
Profile JSON
    ↓ profile_converter reads remote_files
honeyfs/_remote/10.0.1.20/var/backups/wp/db_backup.sql.gz  (actual bytes)
etc/remote_files.json  (index: host+path → honeyfs path + size)
    ↓ at runtime
SCP handler reads index → serves content from honeyfs → creates file in VFS
    ↓
Attacker runs `cat /tmp/db_backup.sql.gz` → real content exists
```

### Honeynet Mode

In honeynet mode, the remote host IS a real Cowrie container with its own pickle/honeyfs. Phase 2 SCP proxy would use paramiko SFTP to actually pull files from the neighbor container, making `remote_files` unnecessary for known hops. The `remote_files` approach remains useful for hosts that exist only in `/etc/hosts` but aren't real containers (e.g. `jenkins-ci`, `backup-nfs`).

## Implementation Plan

**File: `Cowrie/cowrie-src/src/cowrie/commands/scp.py`**

### 1. Fix direction detection in `start()`

```python
# Check ALL args for remote pattern
remote_re = re.compile(r"^(?:\S+@)?[\w.\-]+:.+$")
remote_indices = [i for i, a in enumerate(args) if remote_re.match(a)]

if remote_indices:
    if remote_indices[-1] == len(args) - 1:
        # Remote is last arg → push (outbound)
        self._handle_outbound(args)
    else:
        # Remote is not last arg → pull (inbound from remote)
        self._handle_pull_remote(args, remote_indices)
    return
```

### 2. New `_handle_pull_remote()` method

- Parse remote `user@host:path` from the matched args
- Check if honeynet mode → attempt real SCP proxy (future)
- Otherwise simulate: password prompt + progress bar + fake file creation
- Always call `self.exit()` — never hang

### 3. Handle password interaction for pull

- Write `user@host's password: ` prompt
- Register a callback to accept the password line
- Then write transfer progress and exit
- This matches real SCP behavior and keeps the attacker engaged

## Scope & Complexity

| Item | Effort |
|---|---|
| Fix direction detection in `scp.py` | Small — regex scan all args |
| Simulate pull with progress bar | Medium — password prompt callback + progress output |
| Create file in VFS after pull | Small — `self.fs.mkfile()` |
| Profile schema: add `remote_files` | Small — schema + validation |
| Profile generator: scan scripts for SCP refs | Medium — regex extraction + LLM content generation |
| Profile converter: deploy remote files to honeyfs | Medium — new `_remote/` namespace + index file |
| SCP handler: serve remote file content | Small — read index, copy from honeyfs |
| Honeynet SCP proxy via paramiko SFTP | Large — defer to Phase 3 |

## Phasing

**Phase 1** (immediate): Fix direction detection + simulate pull with progress bar + create stub file in VFS. Prevents the hang and keeps the attacker engaged. No real content yet.

**Phase 2**: Add `remote_files` to profile schema, update profile generator to produce remote file content, update profile converter to deploy to `honeyfs/_remote/`, update SCP handler to serve real content. After this, pulled files have real content that survives `cat`.

**Phase 3** (future): Real SCP proxy in honeynet mode using paramiko SFTP to neighbor Cowrie containers.

## Impact on Other Network Commands

The same pattern applies to other commands that reference profile hosts (`10.0.1.20`, `10.0.1.50`, etc.):
- **SSH** already handles this (simulated login or honeynet proxy)
- **curl/wget** are handled by their own command handlers
- **rsync** and **sftp** are not currently handled — they'd hit the LLM fallback, which is acceptable for now
