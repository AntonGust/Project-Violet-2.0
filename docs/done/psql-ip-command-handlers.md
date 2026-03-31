# Implementation Plan: psql and ip Command Handlers

## Context

Hardening Run 3 (2026-03-30) showed the wordpress_server honeynet passes 200 iterations without honeypot detection, but two command gaps remain:

1. **`psql` on hop 2 (database_server)** — 15 attempts, all `command.failed`. The DB server's core tool doesn't work.
2. **`ip addr` on all hops** — Falls through as `command.failed` with no output. The `_PKG_BINARIES` fix added binary stubs to profile_converter but the Docker image wasn't rebuilt, so the pickle FS used at runtime still lacks `/usr/bin/ip`.

## Fix 1: `ip addr` — txtcmd + Docker Rebuild

### Problem
- `ip` has no native Cowrie handler
- LLM fallback has prequery support (`"ip": ["network_detail"]`) but isn't reached because the binary doesn't exist in the pickle FS at runtime
- The `_PKG_BINARIES` code fix in profile_converter.py is correct but hasn't taken effect because Docker image needs rebuilding

### Approach: txtcmd generation (preferred over native handler)

`ip addr` output is mostly static per-profile — same pattern as `ifconfig`, `netstat` which already have txtcmd generators. A native handler would be overkill.

**Add `ip addr` to `generate_txtcmds()` in `profile_converter.py`:**

```python
# In generate_txtcmds(), after the ifconfig block (~line 880):

# ── ip addr ──
interfaces = profile.get("network", {}).get("interfaces", [])
if interfaces:
    lines = []
    for idx, iface in enumerate(interfaces, 1):
        name = iface.get("name", f"eth{idx-1}")
        ip_addr = iface.get("ip", "127.0.0.1")
        mask = iface.get("netmask", "255.255.255.0")
        mac = iface.get("mac", f"02:42:{random_hex_pair()}:{random_hex_pair()}:{random_hex_pair()}:{random_hex_pair()}")

        # Convert netmask to CIDR prefix
        cidr = sum(bin(int(x)).count('1') for x in mask.split('.'))

        # Calculate broadcast
        ip_parts = [int(x) for x in ip_addr.split('.')]
        mask_parts = [int(x) for x in mask.split('.')]
        bcast = '.'.join(str(ip_parts[i] | (255 - mask_parts[i])) for i in range(4))

        flags = "<LOOPBACK,UP,LOWER_UP>" if name == "lo" else "<BROADCAST,MULTICAST,UP,LOWER_UP>"
        mtu = 65536 if name == "lo" else 1500
        link_type = "loopback" if name == "lo" else "ether"

        lines.append(f"{idx}: {name}: {flags} mtu {mtu} qdisc {'noqueue' if name == 'lo' else 'fq_codel'} state UP group default qlen 1000")
        if name == "lo":
            lines.append(f"    link/{link_type} 00:00:00:00:00:00 brd 00:00:00:00:00:00")
        else:
            lines.append(f"    link/{link_type} {mac} brd ff:ff:ff:ff:ff:ff")
        lines.append(f"    inet {ip_addr}/{cidr} brd {bcast} scope global {name}")
        lines.append(f"       valid_lft forever preferred_lft forever")

    ip_output = "\n".join(lines) + "\n"
    _write_txtcmd(output_dir / "sbin" / "ip", ip_output)       # /sbin/ip
    _write_txtcmd(output_dir / "usr" / "bin" / "ip", ip_output)  # /usr/bin/ip
```

**Limitation:** txtcmds are static — `ip addr show eth0` or `ip route` won't work. But the LLM fallback (which already has `"ip": ["network_detail"]` context) will handle those variants once the binary exists in the pickle FS.

### Files to modify
| File | Change |
|------|--------|
| `Reconfigurator/profile_converter.py` | Add `ip addr` block to `generate_txtcmds()` |

### Verification
- `docker compose build` to rebuild with updated profile_converter
- Run hardening cycle — `ip addr` should return realistic output
- `ip route`, `ip -br addr` will still go to LLM fallback (acceptable)

---

## Fix 2: `psql` Native Handler

### Problem
- No `psql` command handler exists in `Cowrie/cowrie-src/src/cowrie/commands/`
- The database_server profile has PostgreSQL as its core service (port 5432, pgbouncer on 6432)
- Prequery already maps `"psql": ["db_context"]` — LLM fallback would work if it were reached
- But without a registered handler, AND without the binary in pickle FS, `psql` fails silently
- Even with LLM fallback, the interactive `psql` prompt (postgres=#) needs native handling

### Approach: Native handler modeled on mysql.py

Create `psql.py` following the exact same three-tier pattern as `mysql.py`:

```
Native SQL → DB Proxy → LLM Fallback
```

### Architecture

```
Command_psql (HoneyPotCommand)
├── Argument parsing
│   ├── -U <user>        (username, default: current user)
│   ├── -h <host>        (hostname)
│   ├── -d <database>    (database name, also positional)
│   ├── -p <port>        (port, default 5432)
│   ├── -c <command>     (execute SQL and exit)
│   ├── -f <file>        (execute file — stub, route to LLM)
│   ├── -l               (list databases, like \l)
│   ├── --version        (print version and exit)
│   └── --help           (print help and exit)
│
├── Connection simulation
│   ├── _has_postgres_service()  — check profile services
│   ├── _check_credentials()     — validate against .pgpass / profile
│   └── _do_login()              — print banner, show prompt
│
├── Interactive mode (postgres=# prompt)
│   ├── lineReceived()
│   ├── Backslash commands:
│   │   ├── \l, \list    → list databases
│   │   ├── \dt           → list tables
│   │   ├── \du           → list users/roles
│   │   ├── \d <table>    → describe table
│   │   ├── \c <db>       → switch database
│   │   ├── \conninfo     → show connection info
│   │   ├── \q            → quit
│   │   └── \?            → help
│   └── SQL execution (three-tier)
│
├── Three-tier SQL handling
│   ├── _try_native_sql()
│   │   ├── SELECT version()
│   │   ├── SELECT current_user
│   │   ├── SELECT current_database()
│   │   ├── \l / SELECT datname FROM pg_database
│   │   ├── \dt / SELECT tablename FROM pg_tables
│   │   └── SELECT from profile SQL dumps
│   ├── _try_db_proxy()     — execute via pg8000
│   └── _route_to_llm()     — LLM with db_context
│
├── Output formatting
│   ├── _format_table()      — PostgreSQL-style table (column headers + dashes)
│   ├── _format_row_count()  — "(N rows)" footer
│   └── _format_error()      — "ERROR: ..." format
│
└── Signal handling
    ├── handle_CTRL_C  → cancel query
    └── handle_CTRL_D  → \q (quit)
```

### PostgreSQL vs MySQL output differences

The handler MUST produce PostgreSQL-formatted output, not MySQL:

```
MySQL format:                           PostgreSQL format:
+------+--------+                        datname  | datdba
| name | owner  |                       ----------+--------
+------+--------+                        postgres |     10
| mydb | root   |                        appdb    |  16384
+------+--------+                       (2 rows)
2 rows in set (0.00 sec)
```

Key differences:
- No box-drawing (`+---+`) — uses pipe separators and dash underlines
- Row count footer: `(N rows)` or `(N row)` not `N rows in set`
- Prompts: `postgres=#` (superuser) or `postgres=>` (regular user), not `mysql>`
- Backslash meta-commands (`\l`, `\dt`) instead of `SHOW DATABASES`, `SHOW TABLES`
- `SSL connection` line in banner
- Version string: `psql (14.11)` not `mysql Ver 8.0.xx`

### Banner format
```
psql (14.11)
SSL connection (protocol: TLSv1.3, cipher: TLS_AES_256_GCM_SHA384, bits: 256, compression: off)
Type "help" for help.

postgres=#
```

### Native SQL responses (from profile data)

**`\l` / `SELECT datname FROM pg_database`:**
Extract database names from profile's `file_contents` — look for:
- `.pgpass` entries (format: `host:port:database:user:password`)
- `pg_hba.conf` entries
- SQL dumps containing `CREATE DATABASE`
- Environment variables referencing DB names

**`\dt`:**
Extract table names from SQL dump files in profile `file_contents`.

**`SELECT version()`:**
```
PostgreSQL 14.11 on x86_64-pc-linux-gnu, compiled by gcc (GCC) 7.3.1 20180303 (Red Hat 7.3.1-5), 64-bit
```
(Version from profile's `installed_packages` → `postgresql14-server` → `14.11`)

### Profile integration

The handler accesses profile data via:
```python
handler = getattr(self.protocol, "llm_fallback_handler", None)
profile = getattr(handler, "_profile", {}) if handler else {}
```

For DB proxy:
```python
db_proxy = getattr(handler, "_db_proxy", None) if handler else None
```

### Registration

```python
# Bottom of psql.py
commands = {}
commands["/usr/bin/psql"] = Command_psql
commands["/usr/local/bin/psql"] = Command_psql
commands["psql"] = Command_psql
```

Add `"psql"` to `Cowrie/cowrie-src/src/cowrie/commands/__init__.py` `__all__` list.

### Also add to _PKG_BINARIES
The profile_converter already has `"postgresql": ["/usr/bin/psql", ...]` — but the database_server profile uses package name `postgresql14-server` and `postgresql14`. The pattern match `"postgresql" in pkg_name` will match `postgresql14`, so this already works.

### Files to create/modify
| File | Change |
|------|--------|
| `Cowrie/cowrie-src/src/cowrie/commands/psql.py` | **New file** — ~400 lines |
| `Cowrie/cowrie-src/src/cowrie/commands/__init__.py` | Add `"psql"` to `__all__` |

### Estimated size
The mysql.py handler is 693 lines with extensive native SQL parsing. The psql handler can be simpler:
- Skip complex INSERT/CREATE TABLE parsing initially — let DB proxy and LLM handle those
- Focus on: connection simulation, backslash commands, `SELECT version/user/database`, `\l`, `\dt`
- Estimated: ~350-400 lines

---

## Implementation Order

1. **`ip addr` txtcmd** (~20 lines of code) — quick win, low risk
2. **`psql` handler** (~400 lines) — larger, needs Docker rebuild
3. **Docker rebuild** — one rebuild covers both changes
4. **Hardening verification run** — confirm both fixes work

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| psql handler produces wrong format | Use PostgreSQL docs as reference, test with real psql output |
| DB proxy connection fails | Three-tier fallback: native → proxy → LLM. If proxy fails, LLM handles it |
| txtcmd `ip addr` conflicts with LLM fallback | txtcmd only matches exact `ip` command; subcommands like `ip route` fall through to LLM |
| Docker rebuild breaks other things | Run full hardening cycle to verify |
