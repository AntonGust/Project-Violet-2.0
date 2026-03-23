# Design: Service Containers for Honeypot Authenticity

## Problem

When an attacker inside Cowrie runs `redis-cli INFO` or `curl localhost:80`, the LLM generates plausible but inconsistent output. Real service containers would make these interactions protocol-authentic — a port scan shows real open ports, `redis-cli` speaks real RESP protocol, `curl` gets real HTTP responses.

The DB honeypot (MySQL/PostgreSQL) already follows this pattern successfully. This design extends it to Redis and Nginx.

---

## Architecture Overview

Same 3-layer pattern as the database honeypot:

```
Profile JSON  →  extract_service_config()  →  service_config.json
                                                      ↓
deploy_profile()  →  generate_service_compose()  →  docker-compose.override.yml
                                                      ↓
Cowrie runtime  ←  COWRIE_SVC_* env vars  ←  ServiceProxy  ←  real container
```

---

## Phase 1: Redis Service Container

### Why Redis first

- **6MB image**, instant startup, zero dependencies
- Attackers run `redis-cli INFO`, `redis-cli KEYS *`, `redis-cli GET session:*` for credential hunting
- Redis protocol is simple — proxy can be thin
- Several profiles have Redis-like services or session caches

### 1a. Profile Detection: `extract_redis_config()`

**File: `Reconfigurator/service_seed_generator.py`** (new)

Detects Redis if profile has:
- A service named `redis` or `redis-server`
- An installed package `redis-server` or `redis-tools`
- A file `/etc/redis/redis.conf` in `file_contents`

```python
def extract_redis_config(profile: dict) -> dict | None:
    """Extract Redis config from profile, or None if no Redis detected."""
    # Check services
    for svc in profile.get("services", []):
        if "redis" in svc["name"]:
            port = svc.get("ports", [6379])[0]
            break
    else:
        # Check packages
        for pkg in profile.get("installed_packages", []):
            if "redis" in pkg.get("name", ""):
                port = 6379
                break
        else:
            return None

    # Extract password from profile file_contents
    password = _extract_redis_password(profile)

    return {
        "engine": "redis",
        "image": config.REDIS_IMAGE,  # "redis:7-alpine"
        "port": port,
        "password": password,  # None if no auth
    }
```

**Password extraction**: Scan `/etc/redis/redis.conf` for `requirepass <password>`, or `.env` files for `REDIS_PASSWORD=`.

### 1b. Seed Data: `generate_redis_seed()`

Generate a `redis_seed.sh` script that loads lure data via `redis-cli`:

```bash
#!/bin/bash
# Wait for Redis to be ready
until redis-cli ping | grep -q PONG; do sleep 1; done

# Session tokens (credential lures)
redis-cli SET "session:admin:a1b2c3" '{"user":"admin","role":"superadmin","ip":"10.0.1.5"}'
redis-cli SET "session:deploy:d4e5f6" '{"user":"deploy_bot","token":"ghp_xKz9...","repo":"internal/infra"}'
redis-cli EXPIRE "session:admin:a1b2c3" 86400
redis-cli EXPIRE "session:deploy:d4e5f6" 86400

# Application cache
redis-cli SET "config:db_host" "10.0.2.10"
redis-cli SET "config:db_password" "Pr0d_DB_2024!"
redis-cli SET "config:api_key" "sk-proj-..."

# Queue data (looks like a real worker queue)
redis-cli LPUSH "queue:jobs" '{"id":1,"type":"backup","status":"completed"}'
redis-cli LPUSH "queue:jobs" '{"id":2,"type":"deploy","status":"pending"}'

# Pub/sub channel names (visible in PUBSUB CHANNELS)
redis-cli SET "channel:alerts" "active"
redis-cli SET "channel:metrics" "active"
```

The seed data should be **generated from profile context** — if the profile is a `monitoring_stack`, keys should reference Grafana/Prometheus. If it's a `wordpress_server`, keys should reference WordPress sessions and cache.

### 1c. Compose Generation

**Extend `generate_db_compose()` in `honeypot_tools.py`** or create a parallel `generate_svc_compose()`:

```yaml
honeypot-redis:
  image: "redis:7-alpine"
  restart: "no"
  command: >
    redis-server
    --requirepass "${REDIS_PASSWORD:-}"
    --maxmemory 32mb
    --maxmemory-policy allkeys-lru
  volumes:
    - "./cowrie_config/redis_seed:/data/seed:ro"
  networks:
    innet:
      ipv4_address: "172.${RUNID}.0.5"
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 10
```

**Seed loading**: Use a custom entrypoint or a sidecar script. Simplest approach: mount the seed script and run it after Redis is healthy (similar to Docker entrypoint-initdb.d but manual for Redis).

**Alternative (simpler)**: Generate a `redis.conf` with `appendonly no` and pipe seed commands after healthcheck passes, from the host side in `honeypot_tools.py`:

```python
def seed_redis(cowrie_base: Path, run_id: str) -> None:
    """Pipe seed data into the running Redis container."""
    seed_path = cowrie_base / "redis_seed" / "seed.redis"
    if not seed_path.exists():
        return
    container = f"honeypot-redis"  # or per-hop name
    subprocess.run(
        ["docker", "exec", "-i", container, "redis-cli", "--pipe"],
        input=seed_path.read_bytes(),
        timeout=10,
    )
```

### 1d. Cowrie Integration: `RedisProxy`

**File: `Cowrie/cowrie-src/src/cowrie/shell/redis_proxy.py`** (new)

Lighter than DBProxy — Redis protocol is simpler:

```python
class RedisProxy:
    def __init__(self, host: str, port: int, password: str | None):
        self._host = host
        self._port = port
        self._password = password
        self._conn = None

    def execute(self, *args: str, timeout: float = 3.0) -> str:
        """Execute a Redis command and return the response as a string."""
        # Uses raw socket + RESP protocol (no dependency needed)
        # Or use redis-py if available

    def discover(self) -> dict:
        """Return Redis INFO output (server version, keyspace, memory)."""
```

**No external dependency needed**: Redis RESP protocol is trivial to implement with raw sockets:
```
*2\r\n$4\r\nKEYS\r\n$1\r\n*\r\n
```

But if `redis` pip package is available in the Cowrie image, use it for simplicity.

### 1e. Native `redis-cli` Command Handler

**File: `Cowrie/cowrie-src/src/cowrie/commands/redis_cli.py`** (new)

Similar to the MySQL handler pattern:

```python
class Command_redis_cli(HoneyPotCommand):
    def start(self):
        # Parse args: -h host, -p port, -a password, --no-auth-warning
        # If inline command: redis-cli GET key → route to proxy
        # If no command: enter interactive mode (127.0.0.1:6379>)

    def _handle_interactive(self, line):
        # Route each line to RedisProxy.execute()
        # Show response, re-prompt
```

**Supported commands via proxy**: `GET`, `SET`, `KEYS`, `INFO`, `CONFIG GET`, `DBSIZE`, `SELECT`, `SCAN`, `TTL`, `TYPE`, `HGETALL`, `LRANGE`, `SMEMBERS`, `PUBSUB CHANNELS`.

Commands that shouldn't work: `FLUSHALL`, `FLUSHDB`, `SHUTDOWN`, `DEBUG` → return `(error) READONLY You can't write against a read only replica.` or silently reject.

### 1f. Config Additions

```python
# config.py
REDIS_IMAGE = "redis:7-alpine"
REDIS_IP_SUFFIX = "0.5"          # 172.{RUNID}.0.5
REDIS_DEFAULT_PASSWORD = None     # No auth by default

# Per-hop toggle (like chain_db_enabled)
chain_redis_enabled = [False, False, False]
```

---

## Phase 2: Nginx Service Container

### Why Nginx

- **3MB alpine image**, instant startup
- Attackers run `curl localhost`, `curl -I localhost`, `wget localhost`
- Currently LLM generates inconsistent HTML — real Nginx serves actual pages
- Profile already defines what web service is running (WordPress, Gitea, etc.)

### 2a. Profile Detection: `extract_web_config()`

**File: `Reconfigurator/service_seed_generator.py`** (extend)

Detects web server if profile has:
- Service named `nginx`, `apache2`, `httpd`
- Port 80 or 443 in any service
- Files like `/var/www/html/index.html` in `file_contents`

```python
def extract_web_config(profile: dict) -> dict | None:
    """Extract web server config from profile."""
    for svc in profile.get("services", []):
        if svc["name"] in ("nginx", "apache2", "httpd") or 80 in svc.get("ports", []):
            return {
                "engine": "nginx",
                "image": config.NGINX_IMAGE,
                "port": 80,
                "ssl_port": 443 if 443 in svc.get("ports", []) else None,
                "server_name": profile.get("system", {}).get("hostname", "localhost"),
            }
    return None
```

### 2b. Content Generation: `generate_web_content()`

Generate static HTML based on profile type:

| Profile | Web content |
|---------|-------------|
| `wordpress_server` | WordPress login page (`wp-login.php`) + admin dashboard stub |
| `monitoring_stack` | Grafana-like login page |
| `git_server` | Gitea/Gitlab-like login page |
| `dev_workstation` | Simple "It works!" default page |
| Other | Generic "Welcome to {hostname}" page with realistic headers |

**Implementation**: Template HTML files per profile type, rendered with hostname/version substitution.

Write to `cowrie_config/nginx_content/` which gets mounted into the Nginx container.

Also generate `nginx.conf` with:
- `server_tokens off;` (don't expose Nginx version — real servers hide this)
- `server_name {hostname};`
- `root /usr/share/nginx/html;`
- Error pages (403, 404, 500) that look realistic

### 2c. Compose Generation

```yaml
honeypot-nginx:
  image: "nginx:1.25-alpine"
  restart: "no"
  volumes:
    - "./cowrie_config/nginx_content:/usr/share/nginx/html:ro"
    - "./cowrie_config/nginx_conf/default.conf:/etc/nginx/conf.d/default.conf:ro"
  networks:
    innet:
      ipv4_address: "172.${RUNID}.0.6"
  healthcheck:
    test: ["CMD", "wget", "-q", "--spider", "http://localhost/"]
    interval: 5s
    timeout: 3s
    retries: 10
```

### 2d. Cowrie Integration

**No new proxy needed**. Instead, extend the LLM fallback's command handling:

When Cowrie detects `curl localhost:80` or `wget http://localhost`:
1. Rewrite the URL to point to the Nginx container IP (`172.{RUNID}.0.6`)
2. Actually execute the curl/wget from inside the Cowrie container
3. Return the real HTTP response

This is simpler than a proxy class — it's a request rewriter.

**File: `Cowrie/cowrie-src/src/cowrie/shell/http_rewriter.py`** (new)

```python
def rewrite_local_http(command: str, web_host: str) -> str | None:
    """If command targets localhost:80/443, rewrite to real web container."""
    # Match: curl http://localhost, curl -I 127.0.0.1, wget http://localhost:80
    # Replace localhost/127.0.0.1 with web_host IP
    # Return rewritten command, or None if no rewrite needed
```

The existing `curl.py` handler already executes real HTTP requests (it's one of the few Cowrie commands that actually touches the network). We just need to intercept and rewrite the target.

### 2e. Config Additions

```python
# config.py
NGINX_IMAGE = "nginx:1.25-alpine"
NGINX_IP_SUFFIX = "0.6"
chain_nginx_enabled = [False, False, False]
```

---

## Phase 3: LLM Context Enhancement for `docker exec`

### Problem

`docker exec -it nginx /bin/bash` currently falls to LLM fallback. We can't actually give the attacker a shell inside the real Nginx container (too dangerous). But we can make the LLM response much better.

### Solution: Container-aware LLM context

When the LLM fallback handles `docker exec -it <container> /bin/bash`:

1. **Detect the target container** from our native docker handler's container list
2. **Inject rich context** into the LLM prompt:
   - The container's filesystem layout (from the Docker image manifest)
   - The container's running processes (from the image's entrypoint)
   - The container's environment variables
   - The container's network config
3. **Change the prompt hostname** to match the container name (so the LLM generates `root@nginx-proxy:/#` instead of the host prompt)

### Implementation

**File: `Cowrie/cowrie-src/src/cowrie/shell/prequery.py`** — extend `format_container_context()`:

Add a `container_shell_context` key that gets activated when the command matches `docker exec`:

```python
_CONTAINER_FS_TEMPLATES = {
    "nginx": {
        "processes": ["nginx: master process", "nginx: worker process"],
        "key_files": ["/etc/nginx/nginx.conf", "/etc/nginx/conf.d/default.conf", "/usr/share/nginx/html/index.html"],
        "env": ["NGINX_VERSION=1.25.4", "NJS_VERSION=0.8.2"],
    },
    "redis": {
        "processes": ["redis-server *:6379"],
        "key_files": ["/data/dump.rdb", "/usr/local/etc/redis/redis.conf"],
        "env": ["REDIS_VERSION=7.2.4"],
    },
    "mysql": {
        "processes": ["mysqld --user=mysql"],
        "key_files": ["/etc/mysql/my.cnf", "/var/lib/mysql/"],
        "env": ["MYSQL_MAJOR=8.0", "MYSQL_VERSION=8.0.36"],
    },
    # ... more templates
}
```

The LLM would receive:
```
CONTAINER SHELL CONTEXT:
You are now inside the "nginx-proxy" Docker container.
Show prompt as: root@<container_id_short>:/#
Running processes: nginx: master process, nginx: worker process
Key files: /etc/nginx/nginx.conf, /etc/nginx/conf.d/default.conf
Environment: NGINX_VERSION=1.25.4, PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
This is an Alpine Linux container. Use `apk` not `apt`.
```

This makes `docker exec` output realistic without actually giving shell access to a real container.

---

## Implementation Priority

| Phase | What | Resources | Effort | Impact |
|-------|------|-----------|--------|--------|
| **1** | Redis container + proxy + `redis-cli` handler | +6MB RAM/hop | Medium | High — credential lures via real Redis |
| **2** | Nginx container + HTTP rewriter | +3MB RAM/hop | Medium | Medium — real web pages |
| **3** | Container-aware LLM context | +0 RAM | Low | Medium — better `docker exec` responses |

**Suggested order**: 1 → 3 → 2

Phase 1 (Redis) has the highest payoff — real credential data accessible via standard tools. Phase 3 is pure software (no new containers) and improves existing LLM responses. Phase 2 (Nginx) is nice-to-have but less critical since attackers rarely `curl` from an SSH session.

---

## Resource Budget (3-hop honeynet)

Current:
- 3x Cowrie containers (~50MB each)
- 0-3x DB containers (~200MB each for MySQL)
- 1x Kali container

With Phase 1+2:
- +3x Redis (~6MB each) = +18MB
- +3x Nginx (~3MB each) = +9MB
- **Total additional: ~27MB for all hops**

This is negligible. Even with all services enabled on all hops, total RAM stays under 1GB.

---

## Open Questions

1. **Should Redis seed data be profile-specific?** Current design generates context-appropriate keys. Alternative: generic session/cache keys for all profiles.

2. **Should we extend `chain_db_enabled` to a generic `chain_services_enabled` dict?** e.g., `chain_services = [{"db": True, "redis": False, "nginx": True}, ...]` per hop.

3. **Nginx content templates** — how many profile types do we need? Could start with just 2: WordPress login page + generic "It works!".

4. **Redis auth** — should we always enable `requirepass`? Real Redis often has no auth (a common vulnerability). Having no auth makes it more attractive as a target.
