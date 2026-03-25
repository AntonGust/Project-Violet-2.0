# Hardening Fixes: wordpress_server — Run 2026-03-25

## Issues Found (prioritized)

### P0: MySQL queries return empty output (hop 1 & 3)
### P1: nmap command not found (hop 3)
### P2: MySQL "Can't connect" errors suppressed to "Empty set" (hop 3)
### P3: SSH pivot error shows wrong port in error message (hop 1→2)

---

## Fix 1: Native MySQL Result Generation (P0)

**Problem:** The MySQL command handler (`mysql.py`) routes ALL SQL queries to the LLM fallback, which frequently returns empty strings. This is the most critical authenticity issue — `SHOW DATABASES;`, `SHOW TABLES;`, and `SELECT * FROM wp_users;` produced no visible output on hop 1.

**Root cause:** The LLM fallback handler receives the SQL via `_build_mysql_cmd()` → `handle_command()`, but the LLM generates empty or connection-error responses. Even when the DB proxy is available and provides real data, the LLM may ignore or misformat it.

**Solution:** Add native result generation for common SQL queries directly in `mysql.py`, using profile data and DB proxy results. Only fall back to LLM for unrecognized queries.

### Implementation

**File:** `Cowrie/cowrie-src/src/cowrie/commands/mysql.py`

#### A. Add profile-based result tables

Add a `_get_profile_databases()` method that extracts database info from the profile:

```python
def _get_profile_databases(self) -> list[str]:
    """Extract database names from profile file_contents (wp-config, .env, etc.)."""
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    if not handler:
        return ["information_schema", "mysql", "performance_schema"]
    profile = getattr(handler, "_profile", {})

    dbs = {"information_schema", "mysql", "performance_schema", "sys"}
    file_contents = profile.get("file_contents", {})
    for path, content in file_contents.items():
        # Extract DB_NAME from wp-config.php
        m = re.search(r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
        if m:
            dbs.add(m.group(1))
        # Extract DB_NAME from .env
        m = re.search(r"DB_(?:NAME|DATABASE)=(\S+)", content)
        if m:
            dbs.add(m.group(1))
    return sorted(dbs)
```

#### B. Handle common SQL natively before LLM

In `_handle_sql()`, add native handlers for these patterns BEFORE routing to LLM:

| SQL Pattern | Native Response |
|---|---|
| `SHOW DATABASES` | Format from profile `file_contents` (wp-config.php, .env) |
| `SHOW TABLES` | Format from profile SQL dumps (e.g. `wp_migrate_2026.sql`) or LLM with DB proxy discovery |
| `SELECT * FROM wp_users` | Format from profile SQL dumps |
| `SHOW VARIABLES LIKE ...` | Static MySQL defaults |
| `SELECT VERSION()` | Profile's MySQL package version |
| `SELECT USER()` | Current `self._user@localhost` |

Add a `_try_native_sql()` method:

```python
def _try_native_sql(self, sql: str) -> str | None:
    """Try to answer common SQL natively from profile data. Returns None to fall through to LLM."""
    normalized = sql.strip().rstrip(";").upper()

    if normalized == "SHOW DATABASES":
        return self._format_show_databases()

    if normalized == "SHOW TABLES":
        return self._format_show_tables()

    # SELECT from known tables in profile SQL dumps
    if normalized.startswith("SELECT") and "FROM" in normalized:
        return self._try_select_from_profile(sql)

    return None  # Fall through to LLM
```

#### C. Format helpers

```python
def _format_show_databases(self) -> str:
    dbs = self._get_profile_databases()
    lines = ["+--------------------+",
             "| Database           |",
             "+--------------------+"]
    for db in dbs:
        lines.append(f"| {db:<18s} |")
    lines.append("+--------------------+")
    lines.append(f"{len(dbs)} rows in set (0.00 sec)")
    return "\n".join(lines)

def _format_show_tables(self) -> str | None:
    if not self._current_db:
        return "ERROR 1046 (3D000): No database selected"
    tables = self._get_tables_for_db(self._current_db)
    if not tables:
        return None  # Fall through to LLM
    header = f"Tables_in_{self._current_db}"
    max_len = max(len(header), max(len(t) for t in tables))
    sep = "+" + "-" * (max_len + 2) + "+"
    lines = [sep, f"| {header:<{max_len}} |", sep]
    for t in tables:
        lines.append(f"| {t:<{max_len}} |")
    lines.append(sep)
    lines.append(f"{len(tables)} rows in set (0.00 sec)")
    return "\n".join(lines)
```

#### D. Extract tables and data from SQL dumps in profile

Parse `file_contents` entries that look like SQL dumps (contain `CREATE TABLE` and `INSERT INTO`):

```python
def _get_tables_for_db(self, db_name: str) -> list[str]:
    """Extract table names from SQL dumps in profile file_contents."""
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    if not handler:
        return []
    profile = getattr(handler, "_profile", {})
    tables = set()
    for path, content in profile.get("file_contents", {}).items():
        if "CREATE TABLE" not in content:
            continue
        for m in re.finditer(r'CREATE TABLE.*?`(\w+)`', content):
            tables.add(m.group(1))
    return sorted(tables)

def _try_select_from_profile(self, sql: str) -> str | None:
    """Try to answer SELECT queries from SQL dump data in the profile."""
    # Extract table name
    m = re.search(r'FROM\s+`?(\w+)`?', sql, re.IGNORECASE)
    if not m:
        return None
    table_name = m.group(1)

    # Find INSERT data for this table in profile SQL dumps
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    if not handler:
        return None
    profile = getattr(handler, "_profile", {})

    for path, content in profile.get("file_contents", {}).items():
        # Find CREATE TABLE for column names
        create_m = re.search(
            rf'CREATE TABLE.*?`{table_name}`\s*\((.*?)\)\s*ENGINE',
            content, re.DOTALL | re.IGNORECASE
        )
        if not create_m:
            continue

        # Extract column names
        columns = re.findall(r'`(\w+)`', create_m.group(1))

        # Extract INSERT rows
        insert_m = re.search(
            rf"INSERT INTO `{table_name}` VALUES\s*(.+?);\s*$",
            content, re.MULTILINE | re.IGNORECASE
        )
        if not insert_m:
            return self._format_empty_set()

        # Parse row tuples — simplified, works for the profile format
        rows_str = insert_m.group(1)
        rows = re.findall(r'\(([^)]+)\)', rows_str)

        return self._format_select_result(columns, rows, table_name)

    return None  # Table not in profile, fall through to LLM
```

#### E. Integration into `_handle_sql()`

Modify `_handle_sql()` to try native first:

```python
def _handle_sql(self, line: str) -> None:
    stripped = line.strip()
    if stripped.lower() in ("exit", "quit", "\\q", "exit;", "quit;"):
        self.write("Bye\n")
        self.exit()
        return
    if not stripped:
        self._show_prompt()
        return

    # Track USE statements
    normalized = stripped.rstrip(";").strip().lower()
    if normalized.startswith("use "):
        self._current_db = normalized[4:].strip().strip("`\"'")

    # Try native SQL first
    result = self._try_native_sql(stripped)
    if result is not None:
        self.write(result + "\n")
        self._show_prompt()
        return

    # Fall through to LLM
    self._route_to_llm(self._build_mysql_cmd(stripped))
```

Also modify `_run_inline_query()` similarly to try native first.

#### F. Also try DB proxy directly

When the DB proxy is available, use it for direct query execution instead of routing through LLM:

```python
def _try_db_proxy(self, sql: str) -> str | None:
    """Execute SQL against the real DB proxy if available."""
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    if not handler:
        return None
    db_proxy = getattr(handler, "_db_proxy", None)
    if not db_proxy:
        return None

    result = db_proxy.execute(sql)
    if result.get("error"):
        return None  # Fall through
    if not result.get("columns"):
        return "Query OK, 0 rows affected (0.00 sec)"

    return self._format_db_proxy_result(result)
```

Priority chain: `_try_db_proxy()` → `_try_native_sql()` → `_route_to_llm()`

---

## Fix 2: nmap Command Handler (P1)

**Problem:** `nmap` on hop 3 (cicd_runner) returns `command not found`. The attacker tried `nmap -sn` 4 times, got `cowrie.command.failed` each time, and had to resort to blind SSH attempts.

**Solution:** Create a minimal `nmap.py` command handler that delegates to LLM fallback. Since nmap output varies wildly by flags, native parsing isn't worth the effort — the LLM fallback handles this well when given network context.

### Implementation

**New file:** `Cowrie/cowrie-src/src/cowrie/commands/nmap.py`

```python
# ABOUTME: nmap command handler for Cowrie honeypot.
# ABOUTME: Delegates to LLM fallback with network context for realistic output.

from __future__ import annotations
from cowrie.shell.command import HoneyPotCommand
from cowrie.core.config import CowrieConfig

commands = {}
hybrid_llm_enabled = CowrieConfig.getboolean("hybrid_llm", "enabled", fallback=False)


class Command_nmap(HoneyPotCommand):
    def start(self) -> None:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if hybrid_llm_enabled and handler:
            cmd_string = "nmap " + " ".join(self.args)
            d = handler.handle_command(cmd_string)
            d.addCallback(self._write_and_exit)
            d.addErrback(self._error_and_exit)
        else:
            # Minimal static output for -sn (ping scan)
            self.write("Starting Nmap 7.94 ( https://nmap.org )\n")
            self.write("Nmap done: 0 IP addresses (0 hosts up) scanned in 3.02 seconds\n")
            self.exit()

    def _write_and_exit(self, response: str) -> None:
        if response:
            if not response.endswith("\n"):
                response += "\n"
            self.write(response)
        self.exit()

    def _error_and_exit(self, failure) -> None:
        self.write("Starting Nmap 7.94 ( https://nmap.org )\n")
        self.write("Nmap done: 0 IP addresses (0 hosts up) scanned in 3.01 seconds\n")
        self.exit()


commands["nmap"] = Command_nmap
commands["/usr/bin/nmap"] = Command_nmap
commands["/usr/local/bin/nmap"] = Command_nmap
```

**Also:** Register `nmap` in the prequery `_COMMAND_FAMILIES` in `prequery.py` to ensure network context is injected:

```python
# In _COMMAND_FAMILIES dict:
"nmap": ["network_detail"],
```

**Rebuild required:** Yes — Cowrie Docker image needs rebuild.

---

## Fix 3: MySQL Handler Connection Error Suppression (P2)

**Problem:** In `mysql.py:_write_sql_result()`, when the LLM returns a "Can't connect" response, it's suppressed to `"Empty set (0.00 sec)"`. This is incorrect — "Empty set" implies a query executed but returned no rows, while "Can't connect" is a connection error. On hop 3 (no MySQL service), the correct behavior would be to show the connection error at login time and never enter the mysql> shell.

**Solution:** Two changes:

### A. Validate MySQL service at login

In `_do_login()`, check if MySQL service exists in the profile. If not, show connection error instead of banner:

```python
def _do_login(self) -> None:
    if not self._has_mysql_service():
        self.write(
            f"ERROR 2002 (HY000): Can't connect to local MySQL server "
            f"through socket '/var/run/mysqld/mysqld.sock' (2)\n"
        )
        self.exit()
        return
    version = self._get_version()
    self.write(MYSQL_BANNER.format(version=version))
    self._show_prompt()

def _has_mysql_service(self) -> bool:
    handler = getattr(self.protocol, "llm_fallback_handler", None)
    if not handler:
        return False
    profile = getattr(handler, "_profile", {})
    return any(
        "mysql" in s.get("name", "").lower() or "mariadb" in s.get("name", "").lower()
        for s in profile.get("services", [])
    )
```

### B. Remove "Empty set" suppression

In `_write_sql_result()`, if the LLM returns a connection error but we already showed a successful banner, write the actual query result instead of suppressing:

```python
def _write_sql_result(self, response: str) -> None:
    self._llm_pending = False
    self.protocol.llm_pending = False
    if response:
        # Don't suppress connection errors — if we got this far,
        # we already showed a banner. Empty LLM responses are more
        # likely to be formatting issues than real connection errors.
        self.write(response)
        if not response.endswith("\n"):
            self.write("\n")
    if self._exit_after:
        self.exit()
    else:
        self._show_prompt()
```

This change is safe because Fix 1 handles common queries natively — the LLM fallback is only reached for unusual queries.

---

## Fix 4: SSH Pivot Error Message (P3)

**Problem:** First SSH attempt from hop 1 to hop 2 showed `ssh: connect to host 172.10.0.11 port 22: Connection timed out` after `ssh: failed to open shell: Channel closed`. The error mentions port 22 but the command used port 2222. This is a minor issue but the attacker noticed it.

**Root cause investigation needed:** This error is generated by Cowrie's SSH transport layer, not the profile. The likely cause is a race condition where the hop 2 container isn't fully ready when the first connection attempt is made. The "port 22" in the error is suspicious — it may be a hardcoded default in the error template.

**Solution:** Check the SSH error template in Cowrie's transport code.

**File to investigate:** `Cowrie/cowrie-src/src/cowrie/ssh/` — look for "Connection timed out" error templates and ensure they use the actual port from the SSH command.

This is lower priority and may require deeper investigation into the SSH transport layer. **Defer to next hardening cycle** if the other fixes take priority.

---

## Non-Issues (clarified)

### `find / -name "*.conf"` missing MySQL configs
**Not a bug.** MySQL config files end in `.cnf`, not `.conf`. The attacker would need `find / -name "*.cnf"` to find them. The pickle filesystem correctly contains `/etc/mysql/my.cnf` and `/etc/mysql/mysql.conf.d/mysqld.cnf`.

### CHeaT defenses 0% triggered
**Not fixable via code.** The attacker collected credentials but never attempted to use them against external services. Unicode honeytokens and canary URLs only trigger when the attacker tries to USE the tainted credentials. This is a behavioral pattern of the LLM attacker, not a honeypot deficiency.

---

## Implementation Order

1. **Fix 1** (MySQL native results) — Highest impact, fixes the most critical authenticity issue
2. **Fix 2** (nmap handler) — Quick win, standalone new file
3. **Fix 3** (MySQL service check + error suppression) — Depends on Fix 1 being in place
4. **Fix 4** (SSH error port) — Deferred, needs deeper investigation

## Files Modified

| File | Change Type | Fix |
|------|------------|-----|
| `Cowrie/cowrie-src/src/cowrie/commands/mysql.py` | Major edit | Fix 1, Fix 3 |
| `Cowrie/cowrie-src/src/cowrie/commands/nmap.py` | **New file** | Fix 2 |
| `Cowrie/cowrie-src/src/cowrie/shell/prequery.py` | Minor edit (add nmap to families) | Fix 2 |

## Verification

After implementing, re-run hardening:
```
python3 main.py  # same config, Harden_wordpress_server
```

**Expected improvements:**
- `SHOW DATABASES;` returns database list including `wordpress_prod`
- `SELECT * FROM wp_users;` returns user rows from profile SQL dump
- `nmap -sn` on hop 3 returns LLM-generated scan results instead of `command not found`
- MySQL on hop 3 (no MySQL service) rejects connection at login instead of entering mysql> shell

**Docker rebuild required:** Yes, for nmap handler and mysql.py changes.
