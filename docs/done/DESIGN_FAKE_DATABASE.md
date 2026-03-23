# Design: Fake Database Honeypot Service

## Overview

Add an ephemeral database Docker container to the honeypot environment. The database is profile-matched (MySQL or PostgreSQL), auto-seeded with fake data, and integrated with Cowrie's LLM fallback via a hybrid approach: real SQL execution for queries, LLM-formatted output for session framing.

## Version Spoofing Mechanism

Each profile may specify different database versions (e.g., PostgreSQL 12 vs 16, MySQL 5.7 vs 8.0). Rather than downloading different DB images per profile, we run **one fixed DB version internally** and spoof the version string to the attacker via the LLM layer:

- **Fixed images**: `postgres:16` for PostgreSQL, `mysql:8.0` for MySQL
- **Spoofed version**: Extracted from the profile's `installed_packages` or `services` fields
- **LLM instruction**: The `generate_llm_prompt()` appends a `DATABASE VERSION CONTEXT` block instructing the LLM to always report the spoofed version string

The attacker never makes a real TCP connection — all DB commands go through Cowrie's LLM fallback — so the version deception is seamless. The real DB container provides actual data for query results while the LLM handles version banners and session framing.

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                Docker Network (innet)                  │
│              172.{RUNID}.0.0/24                        │
│                                                        │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐  │
│  │   Kali   │   │  Cowrie   │   │   Fake Database  │  │
│  │  .0.2    │──▶│  .0.3    │──▶│   .0.4           │  │
│  │          │   │          │   │                    │  │
│  │ attacker │   │ prequery │   │ MySQL / PostgreSQL │  │
│  └──────────┘   │ + pymysql│   │ + init scripts     │  │
│                 │ / psycopg│   │ + query logging    │  │
│                 └──────────┘   └──────────────────────┘│
└──────────────────────────────────────────────────────┘
```

**Data flow for `mysql -u wp_admin -p` command:**

```
1. Attacker types command in Cowrie SSH session
2. Cowrie can't handle it → llm_fallback.py → build_prompt()
3. prequery detects "mysql" → db_context key
4. NEW: prequery also calls db_query_proxy to run discovery queries
   against the real DB (SHOW DATABASES, SHOW TABLES, sample rows)
5. Real query results injected into LLM context
6. LLM generates realistic mysql shell session using real data
7. For subsequent SQL statements in the "session", same flow repeats
```

## Component Design

### 1. Docker Compose — New `honeypot-db` Service

**File: `docker-compose.yml`**

```yaml
honeypot-db:
  image: "mysql:8.0"           # fixed image; version spoofed via LLM layer
  restart: "no"
  environment:
    MYSQL_ROOT_PASSWORD: "${DB_ROOT_PASSWORD}"
    MYSQL_DATABASE: "${DB_NAME}"
    MYSQL_USER: "${DB_USER}"
    MYSQL_PASSWORD: "${DB_PASSWORD}"
  volumes:
    - "./cowrie_config/db_init:/docker-entrypoint-initdb.d:ro"
    - "./cowrie_config/var/log/db:/var/log/mysql"
  networks:
    innet:
      ipv4_address: "172.${RUNID}.0.4"
  healthcheck:
    test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
    interval: 5s
    timeout: 3s
    retries: 10
```

The service definition is generated dynamically — see section 2.

**Key decisions:**
- Static IP `.0.4` on the existing `innet` bridge network
- Init scripts mounted read-only from `cowrie_config/db_init/`
- Query log mounted to host for research collection
- Health check ensures DB is ready before attacks begin
- `restart: "no"` — container is ephemeral, managed by our lifecycle

### 2. Dynamic Docker Compose Generation

**File: `Blue_Lagoon/honeypot_tools.py` — new function `generate_db_compose()`**

The current `docker-compose.yml` is static. We need to generate the `honeypot-db` service dynamically because the image (mysql vs postgres) and env vars depend on the active profile.

**Approach:** Generate a `docker-compose.override.yml` that adds the DB service. Docker Compose merges overrides automatically.

```python
def generate_db_compose(db_config: dict, cowrie_base: Path) -> None:
    """
    Write docker-compose.override.yml with the honeypot-db service.

    Args:
        db_config: dict with keys: engine, image, env_vars, healthcheck
        cowrie_base: path to cowrie_config/
    """
```

The override file is regenerated on every `deploy_cowrie_config()` call. On reconfiguration, if the new profile uses a different DB engine, the override changes accordingly.

### 3. DB Configuration Extractor

**File: `Reconfigurator/db_seed_generator.py` — new module**

Parses the profile JSON to extract database configuration and generate init SQL.

```python
def extract_db_config(profile: dict) -> dict | None:
    """
    Extract database configuration from a profile.

    Scans file_contents for DB credentials and service list for DB engines.

    Returns:
        {
            "engine": "mysql" | "postgresql",
            "image": "mysql:8.0" | "postgres:14",
            "databases": [
                {
                    "name": "wordpress_prod",
                    "users": [
                        {"username": "wp_admin", "password": "Str0ng_But_Le4ked!", "host": "%"}
                    ]
                }
            ],
            "port": 3306 | 5432,
        }
        or None if no DB service found in profile.
    """
```

**Credential extraction strategy:**
- Parse `wp-config.php` for `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`
- Parse `.env` files for `DB_*` / `DATABASE_URL` patterns
- Parse `.pgpass` files (format: `host:port:db:user:password`)
- Parse `pgbouncer/userlist.txt` for user/password pairs
- Cross-reference with `services[]` to determine engine type

```python
def generate_init_sql(db_config: dict, profile: dict) -> str:
    """
    Generate SQL init script with schema and seed data.

    For MySQL/WordPress:
        - wp_users, wp_posts, wp_options, wp_comments, wp_postmeta, etc.
        - ~200 rows of fake users, posts, comments using deterministic fake data
        - All user accounts from the profile's credentials

    For PostgreSQL:
        - Tables matching the profile's implied application (app_production, etc.)
        - users, transactions, audit_log, sessions tables
        - All user accounts from .pgpass credentials

    Returns:
        SQL string to write to docker-entrypoint-initdb.d/
    """
```

**Seed data generation:**
- Use deterministic fake data (no external dependency on Faker library)
- Hardcoded realistic-looking names, emails, IPs, timestamps
- WordPress schema: standard WP table structure (well-documented, easy to replicate)
- PostgreSQL: generic business app schema with users, transactions, audit_log
- ~500 rows total — enough to look real, fast to init

### 4. DB Query Proxy

**File: `Cowrie/cowrie-src/src/cowrie/shell/db_proxy.py` — new module**

Runs inside the Cowrie process. Connects to the real database and executes queries.

```python
class DBProxy:
    """
    Executes SQL queries against the honeypot database container.
    Used by the LLM fallback to inject real query results into context.
    """

    def __init__(self, engine: str, host: str, port: int,
                 user: str, password: str, database: str):
        self._engine = engine
        self._conn = None
        # Connection params stored, lazy-connect on first query

    def execute(self, sql: str, timeout: float = 5.0) -> dict:
        """
        Execute a SQL statement and return results.

        Returns:
            {
                "columns": ["id", "user_login", "user_email"],
                "rows": [
                    [1, "admin", "admin@wp-prod-01.internal.corp"],
                    ...
                ],
                "row_count": 5,
                "error": None  # or error message string
            }
        """

    def discover(self) -> dict:
        """
        Run discovery queries for LLM context injection.
        Returns schema overview: databases, tables, row counts.
        """
```

**Dependencies added to Cowrie:**
- `pymysql` — pure Python MySQL client (no C extensions, works in distroless)
- `pg8000` — pure Python PostgreSQL client (no C extensions, works in distroless)

These get added to `Cowrie/cowrie-src/requirements.txt`.

**Safety:** No safety restrictions on queries. The database is ephemeral. If the attacker drops tables, they're gone — that's fine and realistic.

### 5. Prequery Integration

**File: `Cowrie/cowrie-src/src/cowrie/shell/prequery.py` — modifications**

The `db_context` handling gets enhanced:

```python
# In _get_context_data(), when key == "db_context":
# After building the existing service/package context,
# also attempt to query the real DB for live data.

elif key == "db_context":
    svcs = [...]  # existing logic
    if not svcs:
        return None

    # NEW: attach live DB data if proxy is available
    result = {"services": svcs, "packages": [...]}
    return result
```

The main integration point is in `llm_fallback.py`'s `build_prompt()`:

```python
# In LLMFallbackHandler.__init__():
self._db_proxy: DBProxy | None = self._init_db_proxy()

# In build_prompt(), after existing db_context handling:
if "db_context" in context_needs and self._db_proxy:
    # Extract SQL from command (e.g., "mysql -e 'SELECT * FROM wp_users'")
    sql = self._extract_sql_from_command(command)
    if sql:
        result = self._db_proxy.execute(sql)
        context_needs["db_query_result"] = format_db_query_result(result)
    else:
        # Discovery mode — attacker just connecting
        discovery = self._db_proxy.discover()
        context_needs["db_discovery"] = format_db_discovery(discovery)
```

### 6. LLM Fallback Enhancements

**File: `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py` — modifications**

The LLM system prompt gets a new section when DB context is present:

```
DATABASE QUERY RESULTS:
The attacker executed: SELECT * FROM wp_users LIMIT 5;
Real query output:
+----+------------+-----------+---------------------+
| ID | user_login | user_email          | user_registered     |
+----+------------+---------------------+---------------------+
|  1 | admin      | admin@company.com   | 2024-01-15 10:23:00 |
...

Format your response as if the attacker is in an interactive mysql session.
Use the EXACT data above — do not invent different values.
```

This gives the LLM real data to format, while it handles the session chrome (welcome banner, prompt, formatting).

### 7. DB Config in Profile JSON

**New optional field in profile schema:**

```json
{
  "database_config": {
    "engine": "mysql",
    "version": "8.0",
    "databases": [
      {
        "name": "wordpress_prod",
        "schema_template": "wordpress",
        "seed_rows": 500
      }
    ]
  }
}
```

This is **optional**. If absent, `extract_db_config()` infers everything from `file_contents` and `services`. The explicit field is for future profiles or when inference isn't sufficient.

### 8. Query Logging

**MySQL** (`my.cnf` mounted into container):
```ini
[mysqld]
general_log = 1
general_log_file = /var/log/mysql/general.log
```

**PostgreSQL** (`postgresql.conf` override):
```ini
log_statement = 'all'
log_destination = 'csvlog'
logging_collector = on
log_directory = '/var/log/postgresql'
```

Logs are mounted to `./cowrie_config/var/log/db/` on the host and preserved per-experiment for research analysis.

### 9. Lifecycle Integration

**Modified files:**

`main.py` — `deploy_cowrie_config()`:
```python
def deploy_cowrie_config(profile: dict) -> dict:
    # ... existing deployment ...

    # NEW: Generate DB init scripts and compose override
    db_config = extract_db_config(profile)
    if db_config:
        init_sql = generate_init_sql(db_config, profile)
        write_db_init_scripts(cowrie_base, db_config, init_sql)
        generate_db_compose(db_config, cowrie_base)
    else:
        remove_db_compose()  # No DB in this profile
```

`Blue_Lagoon/honeypot_tools.py` — `start_dockers()`:
```python
def start_dockers():
    # ... existing build/up ...
    # docker-compose automatically picks up override file
    # No code changes needed for start/stop — compose handles it
```

`Blue_Lagoon/honeypot_tools.py` — `wait_for_cowrie()`:
```python
def wait_for_cowrie(timeout: int = 60):
    # ... existing Cowrie wait ...

    # NEW: Also wait for DB to be healthy
    wait_for_db(timeout=60)

def wait_for_db(timeout: int = 60):
    """Wait for honeypot-db container health check to pass."""
    container_name = f"{runid}-honeypot-db-1"
    # Poll docker inspect for health status
```

**Reconfiguration flow:**
1. `stop_dockers()` — tears down all containers including DB
2. `deploy_cowrie_config(new_profile)` — generates new init SQL, new compose override
3. `start_dockers()` — DB container starts fresh with new schema/data
4. `wait_for_cowrie()` + `wait_for_db()` — both services ready

### 10. DB Host Resolution

**Problem:** `wp-config.php` says `DB_HOST=localhost`. But in Docker, `localhost` inside Cowrie means Cowrie's own container, not the DB container.

**Solution:** The DB container gets a network alias matching what the lure files claim. In the compose override:

```yaml
honeypot-db:
  networks:
    innet:
      ipv4_address: "172.${RUNID}.0.4"
      aliases:
        - localhost    # Won't work — reserved
```

Actually, `localhost` alias won't work in Docker networking. Instead:

**Option A (chosen):** The `db_proxy.py` inside Cowrie knows the real DB IP (`172.{RUNID}.0.4`). The LLM context tells the LLM "the database is accessible and running" — the attacker doesn't see the actual connection, they see LLM-formatted output. The proxy handles the real connection internally.

For the LLM prompt, we add: "MySQL is running locally on port 3306 and is accessible. Database connections work normally."

This works because the attacker never makes a real TCP connection from inside Cowrie — everything goes through the LLM fallback. The proxy is a server-side concern only.

## File Changes Summary

| File | Change |
|------|--------|
| `docker-compose.yml` | No change (override file used instead) |
| `Blue_Lagoon/honeypot_tools.py` | Add `generate_db_compose()`, `wait_for_db()`, update `_compose_env()` |
| `Reconfigurator/db_seed_generator.py` | **New file** — `extract_db_config()`, `generate_init_sql()`, `write_db_init_scripts()` |
| `Cowrie/cowrie-src/src/cowrie/shell/db_proxy.py` | **New file** — `DBProxy` class |
| `Cowrie/cowrie-src/src/cowrie/shell/prequery.py` | Add `format_db_query_result()`, `format_db_discovery()` |
| `Cowrie/cowrie-src/src/cowrie/shell/llm_fallback.py` | Init `DBProxy`, extract SQL from commands, inject real results |
| `Cowrie/cowrie-src/requirements.txt` | Add `pymysql`, `psycopg2-binary` |
| `main.py` | Call DB seed generation in `deploy_cowrie_config()` |
| `config.py` | Add `DB_CONTAINER_IP` constant |

## Seed Data Templates

### WordPress (MySQL)

Tables and approximate row counts:
- `wp_users` (10 rows) — admin, editors, authors, subscribers
- `wp_posts` (50 rows) — published articles, drafts, pages
- `wp_comments` (100 rows) — comments on posts
- `wp_options` (200 rows) — WordPress settings (siteurl, blogname, etc.)
- `wp_postmeta` (100 rows) — post metadata
- `wp_usermeta` (50 rows) — user metadata
- `wp_terms` / `wp_term_taxonomy` (20 rows) — categories, tags
- `wp_links` (5 rows) — blogroll links

### PostgreSQL Business App

Tables and approximate row counts:
- `users` (25 rows) — employee accounts with roles
- `transactions` (200 rows) — financial transactions
- `audit_log` (100 rows) — system audit trail
- `sessions` (50 rows) — active/recent sessions
- `api_keys` (10 rows) — API access tokens
- `config` (30 rows) — application settings

## Open Considerations

1. **Cowrie distroless image**: The runtime uses `gcr.io/distroless/python3-debian12`. Both `pymysql` and `pg8000` are pure Python — no C extensions, works in distroless without issues.

2. **Connection timing**: The DB proxy should lazy-connect and handle connection failures gracefully (DB might not be ready yet when first command arrives).

3. **Multiple databases per profile**: The database_server profile has credentials for multiple DBs. The init script should create all of them.
