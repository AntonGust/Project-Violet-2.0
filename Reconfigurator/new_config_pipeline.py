import json
import logging
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

import config as cfg
from Reconfigurator.profile_distance import is_novel
from Reconfigurator.utils import extract_json
from Utils.llm_client import get_client

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "RagData" / "filesystem_profile_schema.json"

# ---------------------------------------------------------------------------
# Lure categories — minimum counts and descriptions used by the prompt builder
# and the post-generation validator.
# ---------------------------------------------------------------------------
LURE_REQUIREMENTS = {
    "breadcrumb_credentials": {
        "min_count": 4,
        "description": "Files containing plaintext or weakly-obfuscated credentials",
        "examples": [
            ".bash_history with DB commands",
            "backup scripts with hardcoded passwords",
            "wp-config.php / .env with DB creds",
            ".pgpass / .my.cnf",
        ],
    },
    "lateral_movement_targets": {
        "min_count": 2,
        "description": "/etc/hosts entries or SSH configs pointing to other internal hosts",
        "examples": [
            "db-replica-01, jenkins-ci, monitoring in /etc/hosts",
            "~/.ssh/config with Host entries",
            "scripts referencing internal IPs",
        ],
    },
    "privilege_escalation_paths": {
        "min_count": 1,
        "description": "Discoverable privesc opportunities",
        "examples": [
            "non-root user with selective sudo rules",
            "writable cron job",
            "docker group membership",
            "SUID binary",
        ],
    },
    "active_system_indicators": {
        "min_count": 3,
        "description": "Files that make the system feel alive and recently used",
        "examples": [
            "/var/log/auth.log with recent entries",
            "/var/mail/root with messages",
            "recent files in /tmp",
            ".bash_history with varied commands",
            "/var/log/syslog excerpts",
        ],
    },
    "explorable_applications": {
        "min_count": 1,
        "description": "Web apps, databases, or services with discoverable config/data",
        "examples": [
            "WordPress install with plugins",
            "docker-compose.yml referencing services",
            ".git directory with source",
            "Redis/Elasticsearch config",
        ],
    },
    "rabbit_holes": {
        "min_count": 2,
        "description": "Large or complex files that absorb attacker iterations",
        "examples": [
            "Long log files with SQL errors or auth failures",
            "Full config files (nginx.conf, my.cnf)",
            "crontab with many jobs",
            "multiple user home dirs with scattered files",
        ],
    },
}

# Load schema once at module level to avoid repeated disk I/O
with open(SCHEMA_PATH, "r", encoding="utf8") as _f:
    _SCHEMA_TEXT = _f.read()
    _SCHEMA_DICT = json.loads(_SCHEMA_TEXT)

# Pre-compiled regexes for lure validation
_CRED_RE = re.compile(
    r"password|passwd|secret|_key|token|credential|PWD|PASS|pgpass|my\.cnf",
    re.IGNORECASE,
)
_INTERNAL_IP_RE = re.compile(
    r"(?:10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)"
)
_APP_RE = re.compile(
    r"wp-config|docker-compose|\.git|redis\.conf|elasticsearch\.yml|nginx\.conf|apache|my\.cnf|postgresql\.conf|pg_hba\.conf|Jenkinsfile|config\.toml",
    re.IGNORECASE,
)


def query_openai(prompt: str, model: str = None, temperature: float = 0.7) -> str:
    """Query the configured LLM with a prompt and return the generated response."""
    if model is None:
        model = cfg.llm_model_reconfig
    response = get_client().chat.completions.create(
        model=model.value if hasattr(model, "value") else str(model),
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        stream=False,
    )
    return response.choices[0].message.content.strip()


def sample_previous_profiles(experiment_dir, sample_size=5) -> list[dict]:
    """
    Load previous profiles and session data from the experiment directory.
    Returns list of {"profile": dict, "sessions": list | None}.
    """
    experiment_dir = Path(experiment_dir)
    entries = []

    for hp_config_dir in experiment_dir.glob("hp_config_*"):
        config_file = hp_config_dir / "honeypot_config.json"
        if config_file.exists():
            entries.append((hp_config_dir, config_file))

    if not entries:
        return []

    if len(entries) > sample_size:
        entries = random.sample(entries, sample_size)

    results = []
    for hp_config_dir, config_file in entries:
        try:
            with open(config_file, "r", encoding="utf8") as f:
                profile_data = json.load(f)
        except Exception as e:
            log.warning("Error loading profile from %s: %s", config_file, e)
            continue

        sessions_file = hp_config_dir / "sessions.json"
        session_data = None
        if sessions_file.exists():
            try:
                with open(sessions_file, "r", encoding="utf8") as f:
                    session_data = json.load(f)
            except Exception as e:
                log.warning("Error loading sessions from %s: %s", sessions_file, e)

        results.append({"profile": profile_data, "sessions": session_data})

    return results


def build_profile_prompt(schema: str, prev_profiles_with_sessions: list[dict]) -> str:
    """
    Build an LLM prompt to generate a novel filesystem profile.

    Args:
        schema: The JSON schema text for filesystem profiles.
        prev_profiles_with_sessions: List of {"profile": dict, "sessions": list|None}.
    """
    # Build the lure strategy section from LURE_REQUIREMENTS
    lure_section = (
        "## Lure Engagement Strategy\n"
        "Your profile MUST include lures from each of the following categories to maximize "
        "attacker engagement time. Each lure should be a thread the attacker can pull — "
        "a credential that leads to a service, a log that hints at other servers, a config "
        "that reveals an internal network.\n\n"
    )
    for i, (category, info) in enumerate(LURE_REQUIREMENTS.items(), 1):
        pretty_name = category.replace("_", " ").title()
        lure_section += f"### {i}. {pretty_name} (minimum {info['min_count']})\n"
        lure_section += f"{info['description']}.\n"
        lure_section += f"Examples: {', '.join(info['examples'])}.\n\n"

    lure_section += (
        "CRITICAL: Lures must be interconnected. A credential found in .bash_history should "
        "work when tried against a database. An /etc/hosts entry should match an IP found in "
        "a backup script. SSH keys should have comments matching user@hostname patterns that "
        "reference other 'servers'. This interconnectedness is what makes the attacker invest "
        "iterations exploring each thread.\n\n"
    )

    prompt = (
        "You are an expert honeypot designer. Generate a complete filesystem profile JSON "
        "for a Cowrie SSH honeypot. The profile must represent a realistic server persona "
        "that will attract and engage attackers.\n\n"
        "## Requirements\n"
        "- Create a **novel, realistic server persona** with a clear theme/use-case\n"
        "- Include realistic lure files (leaked credentials, config files, SSH keys, database dumps, etc.)\n"
        "- Include believable services, users, and network configuration\n"
        "- The profile must be **significantly different** from all previous profiles listed below\n"
        "- Include at least 3 non-root users with realistic names for the server persona\n"
        "- Include at least 5 lure files in file_contents\n"
        "- Include a descriptive 'description' field summarizing the persona and lures\n"
        "- The `id` and `timestamp` fields will be assigned automatically — you may set them to placeholder values\n"
        "- Include at least one non-root user with SSH access (in accepted_passwords) and a "
        "discoverable privilege escalation path (e.g. sudo rules, docker group, writable cron). "
        "This enables a staged attack: enter as low-privilege user → discover privesc → escalate.\n"
        "- If your file_contents include scripts that reference remote hosts via scp or rsync "
        "(e.g. `scp deploy@10.0.1.20:/var/backups/db.sql /tmp/`), include a `remote_files` "
        "section in the profile with realistic text content for those remote files. This allows "
        "the honeypot to serve believable file content when the attacker tries to SCP files "
        "from the referenced hosts. Example:\n"
        '  `"remote_files": {"10.0.1.20": {"/var/backups/db.sql": '
        '{"content_type": "text", "content": "-- MySQL dump\\nCREATE TABLE users ...", "size": 4096}}}`\n'
        "  Use `content_type: \"text\"` with a `content` field for config files, credentials, SQL dumps. "
        "Use `content_type: \"binary\"` with just a `size` field for archives (.gz, .tar, .zip).\n\n"
        + lure_section
        + "## Output Format\n"
        "Return ONLY a valid JSON object matching the schema below.\n"
        "Do NOT include markdown formatting, code fences, or explanations.\n"
        "Begin with `{` and end with `}`.\n\n"
        f"## JSON Schema\n{schema}\n\n"
    )

    if prev_profiles_with_sessions:
        prompt += "## Previous Profiles (generate something DIFFERENT)\n"
        for i, entry in enumerate(prev_profiles_with_sessions, 1):
            profile = entry["profile"]
            prompt += f"\n### Profile {i}\n"
            prompt += f"- Hostname: {profile.get('system', {}).get('hostname', 'N/A')}\n"
            prompt += f"- OS: {profile.get('system', {}).get('os', 'N/A')}\n"
            prompt += f"- Services: {', '.join(s.get('name', '?') for s in profile.get('services', []))}\n"
            prompt += f"- Description: {profile.get('description', 'N/A')}\n"

            users = [u["name"] for u in profile.get("users", []) if u["name"] != "root"]
            if users:
                prompt += f"- Users: {', '.join(users)}\n"

            sessions = entry.get("sessions")
            if sessions and isinstance(sessions, list):
                tactics = set()
                techniques = set()
                for s in sessions:
                    if isinstance(s, dict):
                        for t in s.get("tactics", []):
                            tactics.add(t)
                        for t in s.get("techniques", []):
                            techniques.add(t)
                if tactics:
                    prompt += f"- Observed tactics: {', '.join(sorted(tactics))}\n"
                if techniques:
                    prompt += f"- Observed techniques: {', '.join(sorted(techniques))}\n"

        prompt += (
            "\n## Novelty Requirement\n"
            "Your profile must have a DIFFERENT theme, different services, different users, "
            "and different lure files than all profiles above. Aim for a completely different "
            "server persona (e.g., if previous profiles were web servers and databases, try "
            "a mail server, IoT gateway, CI/CD runner, game server, VPN node, etc.).\n"
        )

    prompt += "\nGenerate the profile JSON now:\n"
    return prompt


# Regex for scp/rsync remote references: user@host:path
_SCP_REF_RE = re.compile(
    r"(?:scp|rsync)\s+.*?(\S+)@([\w.\-]+):(/\S+)", re.IGNORECASE
)


def _scan_remote_file_refs(profile: dict) -> dict[str, dict[str, dict]]:
    """Scan file_contents for scp/rsync user@host:path patterns.

    Returns a remote_files dict: {host: {path: {content_type, size}}}.
    Only includes hosts that appear in /etc/hosts (i.e. are part of the
    profile's network story).
    """
    file_contents = profile.get("file_contents", {})

    # Build set of known hosts from /etc/hosts
    known_hosts: set[str] = set()
    hosts_content = file_contents.get("/etc/hosts", "")
    for line in hosts_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if parts:
            known_hosts.add(parts[0])
            known_hosts.update(parts[1:])
    # Remove loopback
    known_hosts -= {"localhost", "127.0.0.1", "127.0.1.1", "::1",
                    "ip6-localhost", "ip6-loopback", "ip6-allnodes",
                    "ip6-allrouters", "ff02::1", "ff02::2"}
    # Remove the profile's own hostname
    own_hostname = profile.get("system", {}).get("hostname", "")
    known_hosts.discard(own_hostname)

    remote_files: dict[str, dict[str, dict]] = {}
    for content in file_contents.values():
        for m in _SCP_REF_RE.finditer(content):
            host = m.group(2)
            path = m.group(3)
            if host not in known_hosts:
                continue
            remote_files.setdefault(host, {})[path] = {
                "content_type": "binary",
                "size": random.randint(1024, 5 * 1024 * 1024),
            }

    return remote_files


# Deterministic fallback content for remote files that lack content.
# Keyed by filename suffix or pattern → (content_type, content_generator).
_REMOTE_CONTENT_TEMPLATES: list[tuple[re.Pattern, callable]] = [
    (re.compile(r"\.sql$", re.I), lambda path, host: (
        "text",
        f"-- MySQL dump from {host}\n"
        f"-- Generated by mysqldump\n\n"
        f"CREATE DATABASE IF NOT EXISTS `app_db`;\n"
        f"USE `app_db`;\n\n"
        f"CREATE TABLE `users` (\n"
        f"  `id` int(11) NOT NULL AUTO_INCREMENT,\n"
        f"  `username` varchar(64) NOT NULL,\n"
        f"  `email` varchar(128) DEFAULT NULL,\n"
        f"  `password_hash` varchar(255) NOT NULL,\n"
        f"  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,\n"
        f"  PRIMARY KEY (`id`)\n"
        f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n\n"
        f"INSERT INTO `users` VALUES (1,'admin','admin@internal.corp',"
        f"'$2b$12$LJ3m4ys2Kn0RS.YFHBXH0O',NOW());\n"
        f"INSERT INTO `users` VALUES (2,'deploy','deploy@internal.corp',"
        f"'$2b$12$wZKj8PQm1sT.V3xRK5BzXe',NOW());\n"
    )),
    (re.compile(r"credentials\.xml$", re.I), lambda path, host: (
        "text",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<credentials>\n"
        '  <entry type="password">\n'
        "    <scope>GLOBAL</scope>\n"
        "    <id>deploy-ssh</id>\n"
        "    <username>deploy</username>\n"
        "    <password>d3pl0y_pr0d_2024!</password>\n"
        "  </entry>\n"
        '  <entry type="password">\n'
        "    <scope>GLOBAL</scope>\n"
        "    <id>db-backup</id>\n"
        "    <username>backupuser</username>\n"
        "    <password>Bkp_s3cur3_db#99</password>\n"
        "  </entry>\n"
        "</credentials>\n"
    )),
    (re.compile(r"\.conf$|\.cfg$|\.ini$|\.cnf$", re.I), lambda path, host: (
        "text",
        f"# Configuration from {host}:{path}\n"
        f"[database]\n"
        f"host = localhost\n"
        f"port = 3306\n"
        f"user = app_user\n"
        f"password = Pr0d_DB_p@ss_2024\n"
        f"database = production\n\n"
        f"[redis]\n"
        f"host = 127.0.0.1\n"
        f"port = 6379\n"
        f"password = R3dis_C@che_s3cret\n"
    )),
    (re.compile(r"\.env$", re.I), lambda path, host: (
        "text",
        f"# Environment from {host}\n"
        f"DB_HOST=localhost\n"
        f"DB_USER=webapp\n"
        f"DB_PASSWORD=W3b@pp_DB_2024!\n"
        f"DB_NAME=production\n"
        f"REDIS_URL=redis://:r3d1s_s3cret@localhost:6379/0\n"
        f"SECRET_KEY=a8f5f167f44f4964e6c998dee827110c\n"
        f"AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
        f"AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
    )),
    (re.compile(r"\.yml$|\.yaml$", re.I), lambda path, host: (
        "text",
        f"# Config from {host}:{path}\n"
        f"version: '3.8'\n"
        f"services:\n"
        f"  app:\n"
        f"    image: internal-registry:5000/webapp:latest\n"
        f"    environment:\n"
        f"      DB_PASSWORD: Pr0d_p@ss_2024\n"
        f"      SECRET_KEY: a8f5f167f44f4964e6c998dee827110c\n"
        f"    ports:\n"
        f"      - '8080:8080'\n"
    )),
    (re.compile(r"\.sh$", re.I), lambda path, host: (
        "text",
        f"#!/bin/bash\n"
        f"# Script from {host}:{path}\n"
        f"export MYSQL_PWD='Bkp_r00t_2024!'\n"
        f"mysqldump -u root --all-databases > /var/backups/full_dump.sql\n"
        f"gzip /var/backups/full_dump.sql\n"
    )),
    (re.compile(r"\.log$", re.I), lambda path, host: (
        "text",
        f"2024-03-15 08:12:33 INFO  Starting backup on {host}\n"
        f"2024-03-15 08:12:34 INFO  Connected to database as root@localhost\n"
        f"2024-03-15 08:15:01 INFO  Backup complete: 2.4GB written\n"
        f"2024-03-15 08:15:02 WARN  Disk usage at 78% on /var/backups\n"
        f"2024-03-15 12:00:00 INFO  Starting scheduled backup\n"
        f"2024-03-15 12:00:01 ERROR Connection refused to redis://prod-cache:6379\n"
        f"2024-03-15 12:03:45 INFO  Backup complete: 2.5GB written\n"
    )),
]


def _enrich_remote_files(profile: dict) -> None:
    """Fill in missing content for remote_files entries using templates.

    For entries that have content_type=binary and no content, tries to
    match the filename against known templates and upgrade to text with
    deterministic placeholder content.  Leaves genuinely binary files
    (.gz, .tar, .zip, .bak) as binary stubs.
    """
    remote_files = profile.get("remote_files")
    if not remote_files:
        return

    # Extensions that should stay binary
    binary_exts = re.compile(r"\.(gz|tgz|tar|zip|bz2|xz|bak|img|iso|bin|dat)$", re.I)

    for host, files in remote_files.items():
        for rpath, meta in files.items():
            # Skip if already has text content
            if meta.get("content_type") == "text" and meta.get("content"):
                continue
            # Skip genuinely binary files
            if binary_exts.search(rpath):
                continue
            # Try template match
            for pattern, generator in _REMOTE_CONTENT_TEMPLATES:
                if pattern.search(rpath):
                    content_type, content = generator(rpath, host)
                    meta["content_type"] = content_type
                    meta["content"] = content
                    meta["size"] = len(content.encode("utf-8"))
                    break


def finalize_profile(profile: dict) -> dict:
    """Assign UUID, timestamp, strip unknown keys, and ensure required defaults."""
    # Remove top-level keys not defined in the schema (e.g. $schema, title echoed by the LLM)
    allowed_keys = set(_SCHEMA_DICT.get("properties", {}).keys())
    for key in list(profile.keys()):
        if key not in allowed_keys:
            del profile[key]

    profile["id"] = str(uuid.uuid4())
    profile["timestamp"] = datetime.now(timezone.utc).isoformat()

    # Ensure root user exists
    user_names = [u.get("name") for u in profile.get("users", [])]
    if "root" not in user_names:
        profile.setdefault("users", []).insert(0, {
            "name": "root",
            "uid": 0,
            "gid": 0,
            "home": "/root",
            "shell": "/bin/bash",
            "password_hash": "$6$rounds=656000$salt$fakehashroot",
            "groups": ["root"],
        })

    # Ensure ssh_config.accepted_passwords has root entry
    ssh_config = profile.setdefault("ssh_config", {})
    accepted = ssh_config.setdefault("accepted_passwords", {})
    if "root" not in accepted:
        accepted["root"] = ["root", "123456"]

    # Ensure at least one non-root user has SSH access for staged attacks
    nonroot_users = [u for u in profile.get("users", []) if u.get("name") != "root"
                     and u.get("shell", "").endswith(("/bash", "/sh", "/zsh"))]
    has_nonroot_ssh = any(u["name"] in accepted for u in nonroot_users)
    if not has_nonroot_ssh and nonroot_users:
        # Pick the first shell user and give them a password
        target_user = nonroot_users[0]
        accepted[target_user["name"]] = [target_user["name"] + "123", "123456"]

    # Strip None values from string-typed fields to avoid validation errors
    _strip_nulls(profile)

    # Scan for SCP/rsync references and populate remote_files if any found
    if "remote_files" not in profile:
        remote_files = _scan_remote_file_refs(profile)
        if remote_files:
            profile["remote_files"] = remote_files

    # Fill in missing content for remote_files (LLM may have left some as
    # binary stubs, or the scanner created them without content)
    _enrich_remote_files(profile)

    return profile


def _strip_nulls(obj):
    """Recursively remove dict entries whose value is None, since the schema
    has no nullable fields — a missing key is always better than null."""
    if isinstance(obj, dict):
        for key in list(obj.keys()):
            if obj[key] is None:
                del obj[key]
            else:
                _strip_nulls(obj[key])
    elif isinstance(obj, list):
        for item in obj:
            _strip_nulls(item)


def validate_profile(profile: dict, schema: dict = None) -> bool:
    """Validate a profile against the filesystem profile JSON schema."""
    if schema is None:
        schema = _SCHEMA_DICT
    try:
        jsonschema.validate(instance=profile, schema=schema)
        log.info("Profile is valid according to schema.")
        return True
    except jsonschema.ValidationError as e:
        log.warning("Profile validation error: %s", e.message)
        return False


def validate_lure_coverage(profile: dict) -> tuple[bool, list[str]]:
    """Check that a profile meets minimum lure engagement requirements.

    Returns (passed, missing_categories) where *missing_categories* lists the
    category names that did not meet their minimum count.
    """
    file_contents: dict[str, str] = profile.get("file_contents", {})
    users: list[dict] = profile.get("users", [])
    directory_tree: dict = profile.get("directory_tree", {})

    all_paths = set(file_contents.keys())
    for entries in directory_tree.values():
        for e in entries:
            all_paths.add(e.get("name", ""))

    missing: list[str] = []

    # --- breadcrumb_credentials: files containing password-like strings ---
    cred_count = sum(
        1 for content in file_contents.values() if _CRED_RE.search(content)
    )
    if cred_count < LURE_REQUIREMENTS["breadcrumb_credentials"]["min_count"]:
        missing.append("breadcrumb_credentials")

    # --- lateral_movement_targets: /etc/hosts beyond localhost, ssh config, internal IPs ---
    lateral_count = 0
    hosts_content = file_contents.get("/etc/hosts", "")
    # Count non-localhost, non-comment lines in /etc/hosts
    for line in hosts_content.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "localhost" not in line.lower():
            host_ip = line.split()[0] if line.split() else ""
            if host_ip not in ("127.0.0.1", "127.0.1.1", "::1", "ff02::1", "ff02::2"):
                lateral_count += 1
    # SSH config files
    for path in file_contents:
        if path.endswith("/.ssh/config") or path.endswith("/ssh_config"):
            lateral_count += 1
    # Scripts referencing internal IPs (10.x.x.x, 192.168.x.x, 172.16-31.x.x)
    for content in file_contents.values():
        if _INTERNAL_IP_RE.search(content):
            lateral_count += 1
            break  # count once for scripts
    if lateral_count < LURE_REQUIREMENTS["lateral_movement_targets"]["min_count"]:
        missing.append("lateral_movement_targets")

    # --- privilege_escalation_paths ---
    privesc_count = 0
    for u in users:
        if u.get("name") == "root":
            continue
        if u.get("sudo_rules"):
            privesc_count += 1
        if "docker" in u.get("groups", []):
            privesc_count += 1
    # Writable cron references
    crontabs = profile.get("crontabs", {})
    if crontabs:
        privesc_count += 1
    if privesc_count < LURE_REQUIREMENTS["privilege_escalation_paths"]["min_count"]:
        missing.append("privilege_escalation_paths")

    # --- active_system_indicators ---
    active_count = 0
    for path in file_contents:
        if "/var/log/" in path or "/var/mail/" in path:
            active_count += 1
        if path.endswith(".bash_history"):
            active_count += 1
        if path.startswith("/tmp/"):
            active_count += 1
    if active_count < LURE_REQUIREMENTS["active_system_indicators"]["min_count"]:
        missing.append("active_system_indicators")

    # --- explorable_applications ---
    app_count = 0
    for path in file_contents:
        if _APP_RE.search(path):
            app_count += 1
    if app_count < LURE_REQUIREMENTS["explorable_applications"]["min_count"]:
        missing.append("explorable_applications")

    # --- rabbit_holes: file_contents entries > 500 chars ---
    rabbit_count = sum(1 for c in file_contents.values() if len(c) > 500)
    if rabbit_count < LURE_REQUIREMENTS["rabbit_holes"]["min_count"]:
        missing.append("rabbit_holes")

    return (len(missing) == 0, missing)


def generate_new_profile(experiment_base_path) -> dict | None:
    """
    Main entry point: generate a new filesystem profile for Cowrie.

    1. Sample previous profiles from experiment directory
    2. Build LLM prompt with schema + previous profile summaries
    3. Query LLM to generate a new profile
    4. Validate and check novelty
    5. Retry up to 3 times on failure

    Returns the profile dict, or None if generation fails.
    """
    log.info("Starting profile generation with: %s", experiment_base_path)

    # Sample previous profiles
    prev_data = sample_previous_profiles(experiment_base_path)
    prev_profiles = [entry["profile"] for entry in prev_data]

    # Build prompt
    prompt = build_profile_prompt(_SCHEMA_TEXT, prev_data)

    for attempt in range(1, 4):
        try:
            # Query LLM
            llm_output = query_openai(prompt)

            # Parse JSON
            json_str = extract_json(llm_output)
            if json_str is None:
                log.warning("Attempt %d: No JSON found in LLM output. Retrying...", attempt)
                continue
            profile = json.loads(json_str)

            # Finalize
            profile = finalize_profile(profile)

            # Validate
            if not validate_profile(profile):
                log.warning("Attempt %d: Profile failed validation. Retrying...", attempt)
                continue

            # Check lure coverage
            lure_ok, lure_missing = validate_lure_coverage(profile)
            if not lure_ok:
                log.warning("Attempt %d: Profile missing lure categories: %s. Retrying...", attempt, lure_missing)
                # Append a hint to the prompt for the next attempt
                hint = (
                    "\n\nIMPORTANT: Your previous profile was missing lure content in "
                    f"these categories: {', '.join(lure_missing)}. "
                    "Make sure to include them this time.\n"
                )
                if hint not in prompt:
                    prompt += hint
                continue

            # Check novelty
            if not is_novel(profile, prev_profiles, cfg.profile_novelty_threshold):
                log.warning("Attempt %d: Profile too similar to previous. Retrying...", attempt)
                continue

            log.info("New profile generated with id: %s", profile["id"])
            return profile

        except Exception as e:
            log.error("Attempt %d: Error generating profile: %s", attempt, e)

    log.error("Failed to generate profile after 3 attempts. Aborting.")
    return None


if __name__ == "__main__":
    profile = generate_new_profile(".")
    if profile:
        print(json.dumps(profile, indent=2))
