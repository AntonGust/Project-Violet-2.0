# ABOUTME: Pre-query context injection for the LLM fallback handler.
# ABOUTME: Parses commands before sending to the LLM, identifies what context
# ABOUTME: is needed (packages, services, credentials, paths), and assembles
# ABOUTME: a budget-aware context string — zero extra API calls.

from __future__ import annotations

import re
import shlex
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_WRAPPER_PREFIXES: set[str] = {"sudo", "nohup", "nice", "ionice", "env", "time", "strace", "su", "timeout"}

_CREDENTIAL_KEYWORDS: list[str] = [
    "password", "passwd", "secret", "token", "key", "credential",
    "auth", "login", "mysql_pwd", "pgpassword",
]

MAX_CONTEXT_CHARS: int = 3000

# Command-family to context-key mapping
_COMMAND_FAMILIES: dict[str, list[str]] = {
    # Package managers
    "dpkg": ["packages"],
    "apt": ["packages"],
    "apt-get": ["packages"],
    "yum": ["packages"],
    "rpm": ["packages"],
    "pip": ["packages"],
    "pip3": ["packages"],
    "snap": ["packages"],
    # Service / systemd
    "systemctl": ["services_detail"],
    "service": ["services_detail"],
    "journalctl": ["services_detail"],
    # Network
    "ss": ["network_detail"],
    "netstat": ["network_detail"],
    "ip": ["network_detail"],
    "ifconfig": ["network_detail"],
    "ping": ["network_detail"],
    "traceroute": ["network_detail"],
    "nslookup": ["network_detail"],
    "dig": ["network_detail"],
    "curl": ["network_detail"],
    "wget": ["network_detail"],
    "nmap": ["network_detail"],
    # Database
    "mysql": ["db_context"],
    "mysqldump": ["db_context"],
    "psql": ["db_context"],
    "pg_dump": ["db_context"],
    "pg_dumpall": ["db_context"],
    "pg_restore": ["db_context"],
    "redis-cli": ["db_context"],
    "mongo": ["db_context"],
    "mongodump": ["db_context"],
    # Containers
    "docker": ["container_context"],
    "docker-compose": ["container_context"],
    "podman": ["container_context"],
    "kubectl": ["container_context"],
    # User management
    "useradd": ["users_detail"],
    "userdel": ["users_detail"],
    "usermod": ["users_detail"],
    "passwd": ["users_detail"],
    "chage": ["users_detail"],
    "who": ["users_detail"],
    "w": ["users_detail"],
    "last": ["users_detail"],
    "id": ["users_detail"],
    "groups": ["users_detail"],
    # Cron
    "crontab": ["crontabs"],
    # Filesystem overview
    "find": ["directory_tree"],
    "tree": ["directory_tree"],
    "locate": ["directory_tree"],
    # Environment
    "env": ["environment"],
    "printenv": ["environment"],
    "export": ["environment"],
    "set": ["environment"],
    # Disk
    "df": ["disk_info"],
    "du": ["disk_info"],
    "lsblk": ["disk_info"],
    "fdisk": ["disk_info"],
    "mount": ["disk_info"],
    # Firewall
    "iptables": ["firewall"],
    "ufw": ["firewall"],
    "firewall-cmd": ["firewall"],
    "nft": ["firewall"],
    # Cloud CLIs
    "aws": ["cloud_context"],
    "gcloud": ["cloud_context"],
    "az": ["cloud_context"],
    # CI/CD tools
    "gitlab-runner": ["cicd_context"],
    "gh": ["cicd_context"],
    "jenkins-cli": ["cicd_context"],
    # Supply chain / package managers (extended)
    "npm": ["packages", "supply_chain_context"],
    "yarn": ["packages", "supply_chain_context"],
    "mvn": ["packages", "supply_chain_context"],
    "gradle": ["packages", "supply_chain_context"],
    "python3": ["packages"],
    # Misc reconnaissance
    "getcap": ["privilege_context"],
    "nmap": ["network_detail"],
    "rsync": ["network_detail"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_context_needs(
    command: str,
    profile: dict[str, Any],
    protocol_fs: Any | None = None,
) -> dict[str, Any]:
    """
    Parse a (possibly compound) command and return the union of all context
    needs across sub-commands separated by ``|``, ``&&``, ``||``, ``;``.

    Returns a dict whose keys are either context-type names (``"packages"``,
    ``"services_detail"``, …) or path references (``"path:/etc/passwd"``),
    each mapped to the relevant slice of profile data.
    """
    if not command or not command.strip():
        return {}

    # Split on pipe / logical operators / semicolons
    sub_commands = re.split(r"\s*(?:\|\||&&|[|;])\s*", command)

    merged: dict[str, Any] = {}
    for sub in sub_commands:
        sub = sub.strip()
        if not sub:
            continue
        needs = _extract_single_command_context(sub, profile, protocol_fs)
        merged.update(needs)

    return merged


def resolve_path_context(
    path: str,
    profile: dict[str, Any],
    protocol_fs: Any | None = None,
) -> dict[str, Any] | None:
    """
    Resolve a filesystem path to context information.

    Strategy:
    1. Try ``protocol_fs.exists()`` / ``get_path()`` first (live filesystem).
    2. Fall back to profile JSON (``directory_tree``, ``file_contents``).
    3. Walk parent paths to find child directory listings.

    Returns a dict with path metadata, or ``None`` if nothing found.
    """
    # --- 1. Try live filesystem ---
    if protocol_fs is not None:
        try:
            if protocol_fs.exists(path):
                try:
                    entries = protocol_fs.get_path(path)
                    # get_path returns list of 10-element lists for dirs
                    names = [e[0] for e in entries] if entries else []
                    return {"source": "filesystem", "path": path, "children": names}
                except Exception:
                    # It's a file, not a directory — that's fine
                    return {"source": "filesystem", "path": path, "exists": True}
        except Exception:
            pass

    # --- 2. Check profile ---
    # Direct directory match
    if path in profile.get("directory_tree", {}):
        entries = profile["directory_tree"][path]
        names = [e["name"] for e in entries]
        return {"source": "profile", "path": path, "children": names}

    # File contents match
    if path in profile.get("file_contents", {}):
        content = profile["file_contents"][path]
        # Check if it's a credential file
        is_cred = any(kw in path.lower() for kw in _CREDENTIAL_KEYWORDS)
        result: dict[str, Any] = {
            "source": "profile",
            "path": path,
            "exists": True,
            "has_content": True,
            "is_credential_file": is_cred,
            "preview": content[:200] if not is_cred else "(credential file)",
        }
        # Enrich with directory_tree metadata if available
        from pathlib import PurePosixPath as _PPP
        _parent = str(_PPP(path).parent)
        _name = _PPP(path).name
        if _parent in profile.get("directory_tree", {}):
            for entry in profile["directory_tree"][_parent]:
                if entry["name"] == _name:
                    result["type"] = entry.get("type", "file")
                    result["owner"] = entry.get("owner", "root")
                    result["permissions"] = entry.get("permissions", "0644")
                    break
        return result

    # Check if path appears as a file in any directory_tree entry
    from pathlib import PurePosixPath
    parent = str(PurePosixPath(path).parent)
    name = PurePosixPath(path).name
    if parent in profile.get("directory_tree", {}):
        for entry in profile["directory_tree"][parent]:
            if entry["name"] == name:
                return {
                    "source": "profile",
                    "path": path,
                    "exists": True,
                    "type": entry.get("type", "file"),
                    "owner": entry.get("owner", "root"),
                    "permissions": entry.get("permissions", "0644"),
                }

    # --- 3. Parent-path walking ---
    parts = path.strip("/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        candidate = "/" + "/".join(parts[:i])
        if candidate in profile.get("directory_tree", {}):
            entries = profile["directory_tree"][candidate]
            names = [e["name"] for e in entries]
            return {
                "source": "profile",
                "path": candidate,
                "children": names,
                "note": f"closest parent of {path}",
            }

    return None


def assemble_context(context_needs: dict[str, Any]) -> str:
    """
    Convert the *context_needs* dict into a budget-aware text block.

    Path-specific context is prioritized first, then remaining context types
    fill the budget up to ``MAX_CONTEXT_CHARS``.
    """
    if not context_needs:
        return ""

    sections: list[str] = []
    budget = MAX_CONTEXT_CHARS

    # Path-specific context first (sorted for determinism)
    path_keys = sorted(k for k in context_needs if k.startswith("path:"))
    other_keys = sorted(k for k in context_needs if not k.startswith("path:"))

    for key in path_keys:
        if budget <= 0:
            break
        data = context_needs[key]
        section = _format_path_section(key, data)
        if len(section) <= budget:
            sections.append(section)
            budget -= len(section)
        else:
            sections.append(section[:budget])
            budget = 0

    for key in other_keys:
        if budget <= 0:
            break
        data = context_needs[key]
        # If the value was pre-formatted (e.g. by build_prompt injecting
        # overlay/credential data), use it directly instead of re-formatting.
        if isinstance(data, str):
            section = data
        else:
            formatter = _FORMATTERS.get(key)
            if formatter is None:
                continue
            section = formatter(data)
        if not section:
            continue
        if len(section) <= budget:
            sections.append(section)
            budget -= len(section)
        else:
            sections.append(section[:budget])
            budget = 0

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Path extraction
# ---------------------------------------------------------------------------

def _extract_paths(tokens: list[str], raw_command: str) -> list[str]:
    """
    Extract filesystem paths from command tokens using three tiers:

    1. Positional arguments that look like paths (start with ``/`` or ``./``
       or ``~`` or contain ``/``).
    2. Flag-value pairs using ``=`` (e.g. ``--config=/etc/foo.conf``).
    3. Regex scan of the raw command string (excluding the leading command
       token) for ``/absolute/paths``.
    """
    paths: list[str] = []
    seen: set[str] = set()

    def _add(p: str) -> None:
        # Normalize and deduplicate
        p = p.rstrip("/") if p != "/" else p
        if p and p not in seen:
            seen.add(p)
            paths.append(p)

    # Tier 1: positional args
    for tok in tokens:
        if tok.startswith("-"):
            # Tier 2: flag=value
            if "=" in tok:
                val = tok.split("=", 1)[1]
                if "/" in val:
                    _add(val)
            continue
        if tok.startswith("/") or tok.startswith("./") or tok.startswith("~/"):
            _add(tok)
        elif "/" in tok and not tok.startswith("http"):
            # Relative path with directory separator
            _add(tok)

    # Tier 3: regex fallback for absolute paths not yet captured.
    # Strip the leading command token so we don't match e.g. /usr/bin/python3
    # when it's used as the command itself rather than an argument.
    args_start = raw_command.find(" ")
    args_portion = raw_command[args_start:] if args_start != -1 else ""
    for m in re.finditer(r"(/[a-zA-Z0-9_./-]+)", args_portion):
        _add(m.group(1))

    return paths


# ---------------------------------------------------------------------------
# Single-command parser
# ---------------------------------------------------------------------------

def _extract_single_command_context(
    command: str,
    profile: dict[str, Any],
    protocol_fs: Any | None = None,
) -> dict[str, Any]:
    """
    Parse a single (non-compound) command and return context needs.
    """
    # Tokenize
    try:
        tokens = shlex.split(command)
    except ValueError:
        # Malformed quoting — fall back to simple whitespace split
        tokens = command.split()

    if not tokens:
        return {}

    # Strip wrapper prefixes (but only if there's a command after them)
    while len(tokens) > 1 and tokens[0] in _WRAPPER_PREFIXES:
        tok = tokens.pop(0)
        # 'env' with VAR=val: skip the assignment too
        if tok == "env":
            while len(tokens) > 1 and "=" in tokens[0] and not tokens[0].startswith("-"):
                tokens.pop(0)
        # 'su' with -c: skip to the command string
        elif tok == "su":
            if "-c" in tokens:
                idx = tokens.index("-c")
                tokens = tokens[idx + 1:]
                # Re-tokenize the command string passed to su -c
                if tokens:
                    try:
                        tokens = shlex.split(tokens[0])
                    except ValueError:
                        tokens = tokens[0].split()
                break
            # su without -c but with username — skip flags and username
            while tokens and tokens[0].startswith("-"):
                tokens.pop(0)
            if tokens:
                tokens.pop(0)  # skip username
        # 'timeout' with numeric duration argument
        elif tok == "timeout":
            if tokens and re.match(r"^[\d.]+[smhd]?$", tokens[0]):
                tokens.pop(0)

    if not tokens:
        return {}

    base_cmd = tokens[0]
    needs: dict[str, Any] = {}

    # --- Command-family matching ---
    family_keys = _COMMAND_FAMILIES.get(base_cmd)
    if family_keys:
        for key in family_keys:
            data = _get_context_data(key, profile)
            if data is not None:
                needs[key] = data

    # --- Path extraction ---
    paths = _extract_paths(tokens[1:], command)
    for path in paths:
        resolved = resolve_path_context(path, profile, protocol_fs)
        if resolved is not None:
            needs[f"path:{path}"] = resolved

    return needs


# ---------------------------------------------------------------------------
# Context data retrieval
# ---------------------------------------------------------------------------

def _get_context_data(key: str, profile: dict[str, Any]) -> Any:
    """Retrieve raw context data from the profile for a given context key."""
    if key == "packages":
        pkgs = profile.get("installed_packages", [])
        return pkgs if pkgs else None
    elif key == "services_detail":
        svcs = profile.get("services", [])
        return svcs if svcs else None
    elif key == "network_detail":
        net = profile.get("network", {})
        return net if net else None
    elif key == "db_context":
        # Aggregate database-related info
        svcs = [s for s in profile.get("services", [])
                if any(db in s["name"].lower()
                       for db in ("mysql", "postgres", "pgsql", "mongo", "redis",
                                  "pgbouncer", "mariadb"))]
        if not svcs:
            return None
        return {"services": svcs, "packages": [
            p for p in profile.get("installed_packages", [])
            if any(db in p["name"].lower()
                   for db in ("mysql", "postgres", "pgsql", "mongo", "redis",
                              "pgbouncer", "mariadb"))
        ]}
    elif key == "container_context":
        svcs = [s for s in profile.get("services", [])
                if any(c in s["name"].lower()
                       for c in ("docker", "containerd", "podman", "kube"))]
        pkgs = [p for p in profile.get("installed_packages", [])
                if any(c in p["name"].lower()
                       for c in ("docker", "containerd", "podman", "kube"))]
        if not svcs and not pkgs:
            return None
        result: dict[str, Any] = {"services": svcs, "packages": pkgs}
        # Extract fake containers from docker-compose or profile file_contents
        file_contents = profile.get("file_contents", {})
        containers: list[dict[str, Any]] = []
        for path, content in file_contents.items():
            if "docker-compose" in path or "docker_compose" in path:
                # Extract service names from compose files
                for m in re.finditer(r"^\s{2}(\w[\w-]+):\s*$", content, re.MULTILINE):
                    ct: dict[str, Any] = {"name": m.group(1), "image": "custom"}
                    if "privileged" in content:
                        ct["privileged"] = True
                    vol_section = content[m.end():]
                    vols = re.findall(r"-\s+([/\w.]+:[/\w.]+)", vol_section[:500])
                    if vols:
                        ct["volumes"] = vols[:5]
                    containers.append(ct)
            # Kubernetes token
            if "serviceaccount" in path.lower() or ".kube/config" in path:
                result.setdefault("k8s_contexts", []).append(path)
        # Check for docker.sock in directory tree
        dir_tree = profile.get("directory_tree", {})
        for dir_path, entries in dir_tree.items():
            for entry in entries:
                if entry.get("name") == "docker.sock":
                    result["docker_socket"] = True
        if containers:
            result["containers"] = containers
        return result
    elif key == "users_detail":
        users = profile.get("users", [])
        return users if users else None
    elif key == "crontabs":
        crons = profile.get("crontabs", {})
        return crons if crons else None
    elif key == "directory_tree":
        tree = profile.get("directory_tree", {})
        return tree if tree else None
    elif key == "environment":
        # Synthesize environment from profile
        sys_info = profile.get("system", {})
        return {
            "hostname": sys_info.get("hostname", "localhost"),
            "os": sys_info.get("os", "Linux"),
            "arch": sys_info.get("arch", "x86_64"),
        }
    elif key == "disk_info":
        # Static disk info hint
        return {"hint": "standard disk layout"}
    elif key == "firewall":
        return {"hint": "firewall context"}
    elif key == "cloud_context":
        return _get_cloud_context(profile)
    elif key == "cicd_context":
        return _get_cicd_context(profile)
    elif key == "supply_chain_context":
        return _get_supply_chain_context(profile)
    elif key == "privilege_context":
        return _get_privilege_context(profile)
    return None


def _get_cloud_context(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract cloud CLI context from profile file_contents."""
    file_contents = profile.get("file_contents", {})
    packages = profile.get("installed_packages", [])

    cloud_data: dict[str, Any] = {"credentials": [], "buckets": [], "packages": [], "region": "us-east-1"}
    found = False

    # Check cloud packages
    for pkg in packages:
        name = pkg.get("name", "").lower()
        if any(c in name for c in ("awscli", "aws-cli", "google-cloud", "gcloud", "azure-cli", "az-cli")):
            cloud_data["packages"].append(f"{pkg['name']} {pkg.get('version', '')}")
            found = True

    # Scan file contents for cloud credentials
    for path, content in file_contents.items():
        # AWS credentials
        ak = re.search(r'(?:AWS_ACCESS_KEY_ID|aws_access_key_id)\s*=\s*(\S+)', content)
        sk = re.search(r'(?:AWS_SECRET_ACCESS_KEY|aws_secret_access_key)\s*=\s*(\S+)', content)
        if ak and sk:
            cloud_data["credentials"].append({
                "provider": "aws", "access_key": ak.group(1),
                "secret_key": sk.group(1), "source": path,
            })
            found = True

        # GCP service account
        if '"type": "service_account"' in content:
            proj = re.search(r'"project_id":\s*"([^"]+)"', content)
            cloud_data["credentials"].append({
                "provider": "gcp",
                "project": proj.group(1) if proj else "unknown",
                "source": path,
            })
            found = True

        # Azure connection strings
        az_m = re.search(r'AZURE_(?:STORAGE_)?CONNECTION_STRING\s*=\s*(\S+)', content)
        if az_m:
            cloud_data["credentials"].append({
                "provider": "azure", "connection_string": az_m.group(1)[:30] + "...",
                "source": path,
            })
            found = True

        # S3 buckets
        for bm in re.finditer(r's3://([a-zA-Z0-9._-]+)', content):
            if bm.group(1) not in cloud_data["buckets"]:
                cloud_data["buckets"].append(bm.group(1))
                found = True
        sb = re.search(r'S3_BUCKET\s*=\s*(\S+)', content)
        if sb and sb.group(1) not in cloud_data["buckets"]:
            cloud_data["buckets"].append(sb.group(1))
            found = True

        # Region
        rm = re.search(r'region\s*=\s*([\w-]+)', content)
        if rm:
            cloud_data["region"] = rm.group(1)

    return cloud_data if found else None


def _get_cicd_context(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract CI/CD tool context from profile file_contents."""
    file_contents = profile.get("file_contents", {})
    cicd_data: dict[str, Any] = {"tools": [], "config_files": []}
    found = False

    cicd_patterns = {
        "gitlab": (r"gitlab", r"url\s*=\s*\"([^\"]+)\""),
        "jenkins": (r"jenkins", r"<serverUrl>([^<]+)</serverUrl>"),
        "github": (r"github|gh_token|GITHUB_TOKEN", r"GITHUB_TOKEN\s*=\s*(\S+)"),
    }

    for path, content in file_contents.items():
        for tool, (detect_pat, extract_pat) in cicd_patterns.items():
            if re.search(detect_pat, content, re.IGNORECASE):
                entry: dict[str, str] = {"tool": tool, "file": path}
                url_m = re.search(extract_pat, content)
                if url_m:
                    entry["url"] = url_m.group(1)
                cicd_data["config_files"].append(entry)
                if tool not in cicd_data["tools"]:
                    cicd_data["tools"].append(tool)
                found = True

    return cicd_data if found else None


def _get_supply_chain_context(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Extract supply chain / package registry context from profile file_contents."""
    file_contents = profile.get("file_contents", {})
    sc_data: dict[str, Any] = {"registries": []}
    found = False

    registry_patterns = [
        (r"\.npmrc$", "npm", r"registry\s*=\s*(\S+)"),
        (r"\.pypirc$", "pypi", r"repository\s*[:=]\s*(\S+)"),
        (r"pip\.conf$", "pip", r"index-url\s*=\s*(\S+)"),
        (r"settings\.xml$", "maven", r"<url>([^<]+)</url>"),
        (r"\.yarnrc", "yarn", r"registry\s+\"([^\"]+)\""),
    ]

    for path, content in file_contents.items():
        for path_pat, tool, url_pat in registry_patterns:
            if re.search(path_pat, path):
                entry: dict[str, str] = {"tool": tool, "file": path}
                url_m = re.search(url_pat, content)
                if url_m:
                    entry["url"] = url_m.group(1)
                # Look for tokens/auth
                tok_m = re.search(r'(?:_authToken|token|password)\s*[:=]\s*(\S+)', content)
                if tok_m:
                    entry["has_auth"] = "true"
                sc_data["registries"].append(entry)
                found = True

    return sc_data if found else None


def _get_privilege_context(profile: dict[str, Any]) -> dict[str, Any] | None:
    """Build privilege escalation context for commands like getcap."""
    users = profile.get("users", [])
    priv_data: dict[str, Any] = {"sudo_users": [], "docker_users": [], "suid_hint": True}

    for u in users:
        if u.get("sudo_rules"):
            priv_data["sudo_users"].append({"name": u["name"], "rules": u["sudo_rules"]})
        if "docker" in u.get("groups", []):
            priv_data["docker_users"].append(u["name"])

    return priv_data if (priv_data["sudo_users"] or priv_data["docker_users"]) else None


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_packages(
    data: list[dict[str, str]],
    overlay: list[str] | None = None,
) -> str:
    """Format installed packages list for LLM context."""
    lines = ["INSTALLED PACKAGES:"]
    for pkg in data:
        lines.append(f"  {pkg['name']} {pkg.get('version', '')}")
    if overlay:
        for pkg_name in overlay:
            lines.append(f"  {pkg_name} (newly installed)")
    return "\n".join(lines)


def format_services_detail(data: list[dict[str, Any]]) -> str:
    """Format running services with ports and commands."""
    lines = ["RUNNING SERVICES:"]
    for svc in data:
        ports_str = ",".join(str(p) for p in svc.get("ports", []))
        ports_part = f" (ports: {ports_str})" if ports_str else ""
        lines.append(f"  {svc['name']} [PID {svc.get('pid', '?')}] "
                      f"user={svc.get('user', '?')}{ports_part}")
        if svc.get("command"):
            lines.append(f"    cmd: {svc['command']}")
    return "\n".join(lines)


def format_network_detail(data: dict[str, Any]) -> str:
    """Format network interfaces and listening ports."""
    lines = ["NETWORK:"]
    for iface in data.get("interfaces", []):
        lines.append(f"  {iface['name']}: {iface['ip']} "
                      f"netmask={iface.get('netmask', '?')} "
                      f"mac={iface.get('mac', '?')}")
    return "\n".join(lines)


def format_db_context(
    data: dict[str, Any],
    credential_paths: set[str] | None = None,
    valid_credentials: list[dict[str, str]] | None = None,
) -> str:
    """Format database context with services and optionally credential hints."""
    lines = ["DATABASE CONTEXT:"]
    for svc in data.get("services", []):
        ports_str = ",".join(str(p) for p in svc.get("ports", []))
        lines.append(f"  {svc['name']} [PID {svc.get('pid', '?')}] "
                      f"ports={ports_str}")
    for pkg in data.get("packages", []):
        lines.append(f"  package: {pkg['name']} {pkg.get('version', '')}")
    if credential_paths:
        lines.append("  credential files: " + ", ".join(sorted(credential_paths)))
    if valid_credentials:
        lines.append("  VALID CREDENTIALS (from configuration files on this system):")
        for cred in valid_credentials:
            parts = []
            if cred.get("user"):
                parts.append(f"user={cred['user']}")
            if cred.get("password"):
                parts.append(f"password={cred['password']}")
            if cred.get("database"):
                parts.append(f"database={cred['database']}")
            if cred.get("source"):
                parts.append(f"(from {cred['source']})")
            lines.append(f"    {' '.join(parts)}")
        lines.append("  NOTE: If the user provides these credentials, authentication MUST succeed.")
    return "\n".join(lines)


def format_container_context(data: dict[str, Any]) -> str:
    """Format container/orchestration context with fake running containers."""
    lines = ["CONTAINER CONTEXT:"]
    lines.append("  Docker/container tools are installed and running. Commands MUST succeed.")
    lines.append("  NEVER return 'command not found' for docker/kubectl commands.")
    for svc in data.get("services", []):
        lines.append(f"  service: {svc['name']} [PID {svc.get('pid', '?')}]")
    for pkg in data.get("packages", []):
        lines.append(f"  package: {pkg['name']} {pkg.get('version', '')}")
    # Fake running containers for docker ps
    for ct in data.get("containers", []):
        lines.append(f"  running container: {ct['name']} (image={ct.get('image', 'unknown')}"
                      f", ports={ct.get('ports', '')})")
        if ct.get("privileged"):
            lines.append(f"    WARNING: container is running in --privileged mode")
        if ct.get("volumes"):
            lines.append(f"    volumes: {', '.join(ct['volumes'])}")
    # K8s context
    for kc in data.get("k8s_contexts", []):
        lines.append(f"  k8s context: {kc}")
    if data.get("docker_socket"):
        lines.append("  /var/run/docker.sock is accessible (Docker API available)")
    lines.append("  For 'docker exec -it <c> /bin/bash': simulate entering container with a new prompt")
    lines.append("  For 'docker inspect': return realistic JSON with Mounts, NetworkSettings, Config")
    return "\n".join(lines)


def format_users_detail(data: list[dict[str, Any]]) -> str:
    """Format user accounts with groups and home dirs."""
    lines = ["USERS:"]
    for u in data:
        groups = ",".join(u.get("groups", []))
        lines.append(f"  {u['name']} uid={u['uid']} home={u['home']} "
                      f"shell={u['shell']} groups={groups}")
    return "\n".join(lines)


def format_crontabs(data: dict[str, str]) -> str:
    """Format crontab entries by user."""
    lines = ["CRONTABS:"]
    for user, cron in data.items():
        lines.append(f"  [{user}]")
        for line in cron.strip().split("\n"):
            lines.append(f"    {line}")
    return "\n".join(lines)


def format_directory_tree(data: dict[str, list[dict[str, str]]]) -> str:
    """Format directory tree overview."""
    lines = ["DIRECTORY TREE:"]
    for dir_path, entries in data.items():
        names = [e["name"] for e in entries]
        lines.append(f"  {dir_path}: {', '.join(names)}")
    return "\n".join(lines)


def format_environment(data: dict[str, str]) -> str:
    """Format environment / system variables."""
    lines = ["ENVIRONMENT:"]
    for k, v in data.items():
        lines.append(f"  {k}={v}")
    return "\n".join(lines)


def format_disk_info(data: dict[str, Any]) -> str:
    """Format disk info hint."""
    return "DISK: standard disk layout (use df -h output from txtcmds)"


def format_firewall(data: dict[str, Any]) -> str:
    """Format firewall context hint."""
    return "FIREWALL: firewall rules apply (check iptables/ufw/firewall-cmd)"


def format_cloud_context(data: dict[str, Any]) -> str:
    """Format cloud CLI context for LLM."""
    lines = ["CLOUD CLI CONTEXT:"]
    lines.append("  The cloud CLI tool is installed and configured. Commands MUST succeed with realistic fake data.")
    lines.append("  NEVER return 'command not found' for cloud CLI commands.")
    for pkg in data.get("packages", []):
        lines.append(f"  package: {pkg}")
    lines.append(f"  region: {data.get('region', 'us-east-1')}")
    for cred in data.get("credentials", []):
        provider = cred.get("provider", "unknown")
        if provider == "aws":
            lines.append(f"  AWS credentials (from {cred.get('source', '?')}):")
            lines.append(f"    access_key_id: {cred.get('access_key', '?')}")
            lines.append(f"    account_id: 123456789012")
            lines.append(f"    arn: arn:aws:iam::123456789012:user/deploy")
        elif provider == "gcp":
            lines.append(f"  GCP service account (from {cred.get('source', '?')}):")
            lines.append(f"    project: {cred.get('project', '?')}")
        elif provider == "azure":
            lines.append(f"  Azure connection (from {cred.get('source', '?')})")
    for bucket in data.get("buckets", []):
        lines.append(f"  S3 bucket: {bucket} (contains backup files, date-stamped .sql.gz)")
    lines.append("  For 'aws sts get-caller-identity': return Account=123456789012, Arn=arn:aws:iam::123456789012:user/deploy")
    lines.append("  For 'aws s3 ls': return realistic bucket listing with dates")
    lines.append("  For 'aws ec2 describe-instances': return 2-3 instances in the same VPC")
    return "\n".join(lines)


def format_cicd_context(data: dict[str, Any]) -> str:
    """Format CI/CD tool context for LLM."""
    lines = ["CI/CD CONTEXT:"]
    lines.append("  CI/CD tools are installed. Commands MUST succeed with realistic output.")
    lines.append("  NEVER return 'command not found' for CI/CD tool commands.")
    for entry in data.get("config_files", []):
        lines.append(f"  {entry['tool']} config: {entry['file']}")
        if entry.get("url"):
            lines.append(f"    server: {entry['url']}")
    return "\n".join(lines)


def format_supply_chain_context(data: dict[str, Any]) -> str:
    """Format supply chain / package registry context for LLM."""
    lines = ["SUPPLY CHAIN CONTEXT:"]
    lines.append("  Package manager tools are installed. Commands MUST succeed with realistic output.")
    for reg in data.get("registries", []):
        lines.append(f"  {reg['tool']} registry: {reg.get('url', 'default')}")
        lines.append(f"    config file: {reg['file']}")
        if reg.get("has_auth"):
            lines.append(f"    authentication: configured")
    return "\n".join(lines)


def format_privilege_context(data: dict[str, Any]) -> str:
    """Format privilege escalation context for LLM."""
    lines = ["PRIVILEGE CONTEXT:"]
    for su in data.get("sudo_users", []):
        lines.append(f"  sudo user: {su['name']} — {su['rules']}")
    for du in data.get("docker_users", []):
        lines.append(f"  docker group member: {du}")
    if data.get("suid_hint"):
        lines.append("  For 'getcap -r /': return realistic capabilities on /usr/bin/python3.8 (cap_setuid+ep)")
        lines.append("  For 'find / -perm -4000': return standard SUID binaries plus /usr/bin/pkexec")
    return "\n".join(lines)


def _format_path_section(key: str, data: dict[str, Any]) -> str:
    """Format a path-specific context section."""
    path = key.removeprefix("path:")
    lines = [f"PATH CONTEXT ({path}):"]

    if "children" in data:
        lines.append(f"  directory listing: {', '.join(data['children'])}")
        if data.get("note"):
            lines.append(f"  note: {data['note']}")
    elif data.get("has_content"):
        if data.get("is_credential_file"):
            lines.append("  (credential file exists)")
        elif data.get("preview"):
            lines.append(f"  preview: {data['preview']}")
    elif data.get("exists"):
        info_parts = []
        if data.get("type"):
            info_parts.append(f"type={data['type']}")
        if data.get("owner"):
            info_parts.append(f"owner={data['owner']}")
        if data.get("permissions"):
            info_parts.append(f"perms={data['permissions']}")
        if info_parts:
            lines.append(f"  {' '.join(info_parts)}")
        else:
            lines.append("  (exists)")
    else:
        lines.append("  (not found)")

    return "\n".join(lines)


def extract_db_credentials(profile: dict[str, Any]) -> list[dict[str, str]]:
    """
    Extract database credentials from profile file_contents.

    Scans known config file patterns (wp-config.php, .env, backup scripts)
    for database usernames, passwords, and database names.
    """
    creds: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    file_contents = profile.get("file_contents", {})

    for path, content in file_contents.items():
        # WordPress wp-config.php
        if "wp-config" in path.lower():
            user_m = re.search(r"define\s*\(\s*['\"]DB_USER['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
            pass_m = re.search(r"define\s*\(\s*['\"]DB_PASSWORD['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
            db_m = re.search(r"define\s*\(\s*['\"]DB_NAME['\"]\s*,\s*['\"]([^'\"]+)['\"]", content)
            if user_m and pass_m:
                key = (user_m.group(1), pass_m.group(1))
                if key not in seen:
                    seen.add(key)
                    cred: dict[str, str] = {"user": user_m.group(1), "password": pass_m.group(1), "source": path}
                    if db_m:
                        cred["database"] = db_m.group(1)
                    creds.append(cred)

        # .env files
        if path.endswith(".env"):
            user_m = re.search(r"DB_USER(?:NAME)?=(.+)", content)
            pass_m = re.search(r"DB_PASS(?:WORD)?=(.+)", content)
            db_m = re.search(r"DB_(?:NAME|DATABASE)=(.+)", content)
            if user_m and pass_m:
                key = (user_m.group(1).strip(), pass_m.group(1).strip())
                if key not in seen:
                    seen.add(key)
                    cred = {"user": user_m.group(1).strip(), "password": pass_m.group(1).strip(), "source": path}
                    if db_m:
                        cred["database"] = db_m.group(1).strip()
                    creds.append(cred)

        # Shell scripts with MYSQL_PWD or -p'password'
        if path.endswith(".sh"):
            # MYSQL_PWD='password' ... -u user
            pwd_m = re.search(r"MYSQL_PWD=['\"]?([^'\";\s]+)", content)
            user_m = re.search(r"-u\s+(\S+)", content)
            if pwd_m and user_m:
                key = (user_m.group(1), pwd_m.group(1))
                if key not in seen:
                    seen.add(key)
                    creds.append({"user": user_m.group(1), "password": pwd_m.group(1), "source": path})

    return creds


def format_db_query_result(result: dict[str, Any]) -> str:
    """Format real DB query results as an ASCII table for LLM context."""
    if result.get("error"):
        return f"DATABASE QUERY ERROR:\n  {result['error']}"

    columns = result.get("columns", [])
    rows = result.get("rows", [])
    row_count = result.get("row_count", 0)

    if not columns:
        return f"DATABASE QUERY RESULT:\n  Query OK, {row_count} row(s) affected"

    # Calculate column widths
    widths = [len(str(c)) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(str(val)))

    # Cap column widths to 40 chars
    widths = [min(w, 40) for w in widths]

    # Build ASCII table
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    header = "|" + "|".join(f" {str(c):<{w}} " for c, w in zip(columns, widths)) + "|"

    lines = ["DATABASE QUERY RESULT:", sep, header, sep]
    for row in rows[:50]:  # Limit display rows
        cells = []
        for i, val in enumerate(row):
            w = widths[i] if i < len(widths) else 10
            s = str(val)[:w]
            cells.append(f" {s:<{w}} ")
        lines.append("|" + "|".join(cells) + "|")
    lines.append(sep)

    if row_count > len(rows):
        lines.append(f"  ({row_count} total rows, showing first {len(rows)})")
    else:
        lines.append(f"  {len(rows)} row(s) in set")

    return "\n".join(lines)


def format_db_discovery(discovery: dict[str, Any]) -> str:
    """Format DB schema overview for LLM context."""
    if discovery.get("error"):
        return f"DATABASE DISCOVERY ERROR:\n  {discovery['error']}"

    engine = discovery.get("engine", "unknown")
    lines = [f"DATABASE SCHEMA OVERVIEW ({engine}):"]

    for db in discovery.get("databases", []):
        lines.append(f"  Database: {db['name']}")
        for table in db.get("tables", []):
            count = table.get("row_count", "?")
            lines.append(f"    - {table['name']} ({count} rows)")

    return "\n".join(lines)


# Formatter dispatch table
_FORMATTERS: dict[str, Any] = {
    "packages": format_packages,
    "services_detail": format_services_detail,
    "network_detail": format_network_detail,
    "db_context": format_db_context,
    "container_context": format_container_context,
    "users_detail": format_users_detail,
    "crontabs": format_crontabs,
    "directory_tree": format_directory_tree,
    "environment": format_environment,
    "disk_info": format_disk_info,
    "firewall": format_firewall,
    "cloud_context": format_cloud_context,
    "cicd_context": format_cicd_context,
    "supply_chain_context": format_supply_chain_context,
    "privilege_context": format_privilege_context,
}
