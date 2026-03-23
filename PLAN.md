# Demo Mode Implementation Plan

## Context

We need a **Demo Mode** in the main menu that showcases the honeypot's capabilities without running a full Sangria experiment. It loads a profile, spins up Cowrie, connects via SSH directly (no Kali, no Sangria), and runs a scripted sequence of commands demonstrating built-in commands, LLM-powered responses (vim, htop, docker, etc.), and credential breadcrumbs. LLM responses must be cached so repeated demo runs don't hit the API.

---

## Files to Create

### 1. `demo.py` (~250 lines) — Demo orchestrator
- `DemoRunner` class with `setup()`, `connect_ssh()`, `run_demo()`, `teardown()`
- Scripted command sequence organized into themed sections
- Typewriter-style presentation with narration
- Speed modes: normal / fast / interactive
- SSH via pexpect directly to Cowrie (port `22${RUNID}`, credentials from profile)

### 2. `Utils/llm_cache.py` (~80 lines) — Host-side cache utility
- Helper module used by the Cowrie-side cache implementation
- `normalize_cache_key(command)` — strip, collapse whitespace, lowercase
- `load_cache(path)` / `save_cache(path, data)` — JSON read/write
- Cache file format:
  ```json
  {
    "profile_hash": "<sha256>",
    "entries": {
      "<normalized_command>": { "response": "...", "timestamp": "..." }
    }
  }
  ```

---

## Files to Modify

### 3. `docker-compose.yml` — Expose Cowrie SSH port to host
Add port mapping to `cowrie` service:
```yaml
cowrie:
    build: Cowrie/cowrie-src
    restart: always
    ports:
      - "22${RUNID}:2222"    # Direct SSH for demo mode
```
This lets the demo SSH directly to `localhost:22${RUNID}` without going through Kali.

### 4. `main_menu.py` — Add "Demo Mode" menu option
- Add `"Demo Mode"` to `show_main_menu()` choices (after "Start New Experiment")
- Add `run_demo_mode()` function:
  - Profile selection (reuse existing `_discover_profiles()` pattern from settings)
  - Speed selection (normal/fast/interactive)
  - Launch `DemoRunner`, handle Ctrl+C, ensure teardown

### 5. `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py` — Add LLM response caching
Location: `handle_command()` method (line 552-590)

**Cache integration point** — between prompt build and LLM call:
```python
@inlineCallbacks
def handle_command(self, command):
    # Check cache BEFORE building prompt (saves context assembly cost)
    cache_key = self._normalize_cache_key(command)
    cached = self._check_cache(cache_key)
    if cached is not None:
        log.msg(f"HybridLLM: Cache hit for: {command!r}")
        self.history.append({"role": "user", "content": command})
        self.history.append({"role": "assistant", "content": cached})
        impact = self._classify_impact(command)
        self.state_register.add_change(command, cached, impact)
        self._detect_installs(command)
        return cached

    # Original path: build prompt, call LLM
    messages = self.build_prompt(command)
    response = yield self._llm_client.get_response(messages)
    if not response:
        return ""

    # Store in cache
    self._store_cache(cache_key, response)

    # Existing: update history, state, detect installs
    ...
```

**New methods on `LLMFallbackHandler`:**
- `_load_cache()` — read from `/cowrie/cowrie-git/var/llm_cache.json` (mounted volume → `cowrie_config/var/llm_cache.json` on host)
- `_check_cache(key)` → `str | None`
- `_store_cache(key, response)` — write-through to disk
- `_normalize_cache_key(command)` — strip, collapse whitespace, lowercase

**Cache is class-level** (shared across sessions) since it's profile-scoped. Invalidated when `profile_hash` changes (checked on `_load_cache()`).

**Cache file location:** `cowrie_config/var/llm_cache.json` (persists across container restarts via volume mount)

---

## Demo Script (Profile-Adaptive)

The demo script dynamically builds commands from the loaded profile. Each section has a fixed "skeleton" of generic commands plus profile-derived commands.

### Section 1: System Reconnaissance (always the same — built-in)
```
whoami, uname -a, hostname, id, uptime, cat /etc/os-release
```

### Section 2: Filesystem & Credential Discovery (profile-adaptive)
- Always: `ls -la /root`, `cat /root/.bash_history`
- Derived: iterate `profile["file_contents"]` keys, pick files matching credential patterns (`.env`, `wp-config`, `.ssh/id_rsa`, `.pgpass`, etc.)
- Derived: `cat /etc/hosts`, `cat` any SSH config files found

### Section 3: Network & Services (profile-adaptive)
- Always: `ifconfig`, `netstat -tlnp`, `ps aux`
- Derived: for each service in `profile["services"]`, run `systemctl status <service_name>` (LLM-powered)

### Section 4: LLM-Powered Dynamic Responses (cached after first run)
- Always: `docker ps`, `htop`, `df -h`, `free -m`, `crontab -l`
- Derived: `vim <first file_content path>` to demo editor simulation

### Section 5: Lateral Movement Breadcrumbs (profile-adaptive)
- Derived: iterate `profile["file_contents"]` for paths containing `backup`, `.docker`, `.kube`, `.npmrc`, `jenkins`, `deploy` — cat each

**Helper function:** `build_demo_commands(profile) -> list[Section]` reads the profile and returns the full command sequence. This keeps `demo.py` clean and testable.

---

## User Flow

1. Main menu → "Demo Mode"
2. Select profile (wordpress_server / database_server / cicd_runner)
3. Select speed (Normal / Fast / Interactive)
4. System deploys profile → starts Docker → waits for Cowrie → SSH connects
5. Scripted demo runs with section headers, narration, and formatted output
6. Summary printed (commands run, cache stats)
7. Docker containers stopped

---

## Implementation Order

1. `docker-compose.yml` — add port mapping (1 line)
2. `Cowrie/.../llm_fallback.py` — add caching to `handle_command()` (~50 lines)
3. `demo.py` — demo runner with SSH + scripted commands (~250 lines)
4. `main_menu.py` — add menu entry + `run_demo_mode()` (~50 lines)

---

## Verification

1. **First run:** `python main_menu.py` → Demo Mode → wordpress_server → Normal speed
   - All sections execute, LLM commands hit API, cache file created at `cowrie_config/var/llm_cache.json`
2. **Second run:** Same profile — LLM commands served from cache (check Cowrie logs for "Cache hit" messages)
3. **Profile change:** Run with different profile — cache miss, new entries created
4. **Ctrl+C:** Interrupt mid-demo — verify Docker containers are cleaned up
5. **No Docker:** Run without Docker running — verify clean error message
