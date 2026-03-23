"""Lure Enrichment Agent — extends honeypot profiles with additional lure
categories and interconnected attack-path chains."""

import copy
import json
import logging
import re
from typing import Any

from Reconfigurator.new_config_pipeline import (
    LURE_REQUIREMENTS,
    query_openai,
    validate_lure_coverage,
    validate_profile,
)
from Reconfigurator.utils import extract_json

log = logging.getLogger(__name__)


def _pkg_names(packages: list[Any]) -> set[str]:
    """Extract package name strings from a list that may contain plain strings
    or dicts with a 'name' key."""
    names: set[str] = set()
    for pkg in packages:
        if isinstance(pkg, dict):
            names.add(pkg.get("name", ""))
        else:
            names.add(str(pkg))
    return names

# ---------------------------------------------------------------------------
# Extended lure categories (4 new, on top of the original 6)
# ---------------------------------------------------------------------------
EXTENDED_LURE_REQUIREMENTS = {
    "cloud_credentials": {
        "min_count": 1,
        "description": "Cloud provider credentials and config files",
        "examples": [
            "AWS keys in .env or ~/.aws/credentials",
            "GCP service account JSON",
            "Azure connection strings",
        ],
    },
    "container_escape_paths": {
        "min_count": 1,
        "description": "Container breakout and orchestration artifacts",
        "examples": [
            "docker.sock mount",
            "privileged container flag in compose",
            "K8s service account tokens under /var/run/secrets",
        ],
    },
    "cicd_tokens": {
        "min_count": 1,
        "description": "CI/CD pipeline tokens and config files",
        "examples": [
            ".gitlab-ci.yml with tokens",
            "~/.config/gh/hosts.yml",
            "Jenkins API tokens",
        ],
    },
    "supply_chain_artifacts": {
        "min_count": 1,
        "description": "Package registry credentials and private registry config",
        "examples": [
            ".npmrc / .pypirc with auth tokens",
            "private registry URLs",
            "settings.xml with credentials",
        ],
    },
}

# Merge all requirements for unified iteration
ALL_LURE_REQUIREMENTS = {**LURE_REQUIREMENTS, **EXTENDED_LURE_REQUIREMENTS}

# ---------------------------------------------------------------------------
# Detection regexes for the 4 new categories
# ---------------------------------------------------------------------------
_CLOUD_CRED_RE = re.compile(
    r"AKIA[0-9A-Z]{16}"          # AWS access key prefix
    r"|aws_secret_access_key"
    r"|aws_access_key_id"
    r"|credentials\]"             # ~/.aws/credentials section header
    r"|service_account"
    r"|\"type\":\s*\"service_account\""
    r"|AZURE_STORAGE|AZURE_CLIENT|AccountKey=",
    re.IGNORECASE,
)

_CONTAINER_ESCAPE_RE = re.compile(
    r"docker\.sock"
    r"|privileged:\s*true"
    r"|/var/run/secrets/kubernetes"
    r"|serviceaccount/token"
    r"|hostPID:\s*true"
    r"|hostNetwork:\s*true",
    re.IGNORECASE,
)

_CICD_TOKEN_RE = re.compile(
    r"gitlab-ci\.yml"
    r"|GITLAB_TOKEN"
    r"|gh_token"
    r"|hosts\.yml"
    r"|JENKINS_API_TOKEN"
    r"|jenkins.*token"
    r"|GITHUB_TOKEN"
    r"|CI_JOB_TOKEN",
    re.IGNORECASE,
)

_SUPPLY_CHAIN_RE = re.compile(
    r"\.npmrc"
    r"|\.pypirc"
    r"|_authToken"
    r"|registry\.npmjs"
    r"|pypi\.org.*token"
    r"|settings\.xml.*password"
    r"|<server>.*<password>",
    re.IGNORECASE,
)


def analyze_lure_gaps(profile: dict) -> dict:
    """Rule-based gap analysis across all 10 lure categories.

    Returns a dict keyed by category name with:
        count   – how many items were detected
        min     – required minimum
        satisfied – whether count >= min
        details – human-readable summary
    """
    file_contents: dict[str, str] = profile.get("file_contents", {})
    all_text = "\n".join(file_contents.values())
    all_paths = "\n".join(file_contents.keys())

    # Reuse the original 6 categories from validate_lure_coverage
    _, missing_original = validate_lure_coverage(profile)
    report: dict = {}
    for cat, info in LURE_REQUIREMENTS.items():
        satisfied = cat not in missing_original
        report[cat] = {
            "count": info["min_count"] if satisfied else 0,
            "min": info["min_count"],
            "satisfied": satisfied,
            "details": "OK" if satisfied else f"Missing {info['description']}",
        }

    # --- cloud_credentials ---
    cloud_count = sum(
        1 for content in file_contents.values() if _CLOUD_CRED_RE.search(content)
    )
    cloud_min = EXTENDED_LURE_REQUIREMENTS["cloud_credentials"]["min_count"]
    report["cloud_credentials"] = {
        "count": cloud_count,
        "min": cloud_min,
        "satisfied": cloud_count >= cloud_min,
        "details": "OK" if cloud_count >= cloud_min else "No cloud credential files found",
    }

    # --- container_escape_paths ---
    container_count = sum(
        1 for content in file_contents.values() if _CONTAINER_ESCAPE_RE.search(content)
    )
    # Also check paths for docker.sock references
    container_count += sum(
        1 for path in file_contents if "docker.sock" in path
    )
    container_min = EXTENDED_LURE_REQUIREMENTS["container_escape_paths"]["min_count"]
    report["container_escape_paths"] = {
        "count": container_count,
        "min": container_min,
        "satisfied": container_count >= container_min,
        "details": "OK" if container_count >= container_min else "No container escape artifacts found",
    }

    # --- cicd_tokens ---
    cicd_count = 0
    for path, content in file_contents.items():
        if _CICD_TOKEN_RE.search(path) or _CICD_TOKEN_RE.search(content):
            cicd_count += 1
    cicd_min = EXTENDED_LURE_REQUIREMENTS["cicd_tokens"]["min_count"]
    report["cicd_tokens"] = {
        "count": cicd_count,
        "min": cicd_min,
        "satisfied": cicd_count >= cicd_min,
        "details": "OK" if cicd_count >= cicd_min else "No CI/CD token files found",
    }

    # --- supply_chain_artifacts ---
    supply_count = 0
    for path, content in file_contents.items():
        if _SUPPLY_CHAIN_RE.search(path) or _SUPPLY_CHAIN_RE.search(content):
            supply_count += 1
    supply_min = EXTENDED_LURE_REQUIREMENTS["supply_chain_artifacts"]["min_count"]
    report["supply_chain_artifacts"] = {
        "count": supply_count,
        "min": supply_min,
        "satisfied": supply_count >= supply_min,
        "details": "OK" if supply_count >= supply_min else "No supply chain artifacts found",
    }

    return report


def _build_enrichment_prompt(profile: dict, gap_report: dict) -> str:
    """Build the LLM prompt for lure enrichment."""
    system = profile.get("system", {})
    services = profile.get("services", [])
    users = profile.get("users", [])
    packages = profile.get("installed_packages", [])
    file_paths = list(profile.get("file_contents", {}).keys())
    hosts_content = profile.get("file_contents", {}).get("/etc/hosts", "")

    # Compact profile summary
    summary = (
        f"Hostname: {system.get('hostname', 'unknown')}\n"
        f"OS: {system.get('os', 'unknown')}\n"
        f"Services: {', '.join(s.get('name', '?') for s in services)}\n"
        f"Users: {', '.join(u.get('name', '?') for u in users)}\n"
        f"Installed packages: {', '.join(sorted(_pkg_names(packages)))}\n"
        f"Existing file paths ({len(file_paths)}):\n"
    )
    for p in file_paths:
        summary += f"  - {p}\n"
    if hosts_content:
        summary += f"/etc/hosts content:\n{hosts_content}\n"

    # Gap report section
    gaps_section = "## Lure Gaps to Fill\n"
    unsatisfied = {k: v for k, v in gap_report.items() if not v["satisfied"]}
    if not unsatisfied:
        gaps_section += "All categories satisfied — add lure chains only.\n"
    else:
        for cat, info in unsatisfied.items():
            pretty = cat.replace("_", " ").title()
            req = ALL_LURE_REQUIREMENTS.get(cat, {})
            gaps_section += (
                f"- **{pretty}** (need {info['min']}, have {info['count']}): "
                f"{req.get('description', '')}. "
                f"Examples: {', '.join(req.get('examples', []))}\n"
            )

    prompt = f"""You are an expert honeypot lure designer. Given the following honeypot profile summary, generate additional lure content to fill gaps and create interconnected attack-path chains.

## Current Profile
{summary}

{gaps_section}

## Instructions
Generate a JSON object with these keys:

1. **file_contents_additions**: dict of {{path: content}} for new lure files to add.
   - Paths must be absolute (e.g. "/home/deploy/.aws/credentials")
   - Content must be realistic and consistent with the profile's hostname, users, and services
   - Credentials in files must reference services that exist in the profile

2. **directory_tree_additions**: dict of {{parent_dir: [entries]}} where each entry is
   {{"name": str, "type": "file"|"dir", "permissions": str, "owner": str, "group": str, "size": int}}

3. **installed_packages_additions**: list of package names to add (e.g. ["awscli", "docker-ce"])

4. **users_additions**: list of user dicts to add (only if needed for new lures). Each:
   {{"name": str, "uid": int, "gid": int, "home": str, "shell": str, "groups": [str]}}

5. **lure_chains**: list of interconnected attack paths, each:
   {{"chain_id": str, "name": str, "steps": [{{"file": path, "discovery_hint": str, "leads_to": path_or_null}}]}}
   Each chain should represent a realistic breadcrumb trail (credential → service → lateral movement).

## Constraints
- New files MUST be consistent with existing hostname, users, and services
- Credential values must match services present in the profile
- Internal IPs in new files must appear in /etc/hosts (add /etc/hosts update if needed)
- Do NOT duplicate existing file paths
- Generate at least one lure chain connecting 3+ steps

Return ONLY a valid JSON object. No markdown, no explanation.
"""
    return prompt


def _merge_patch(profile: dict, patch: dict) -> tuple[dict, list]:
    """Safely merge an LLM-generated lure patch into the profile.

    Returns (updated_profile, lure_chains).
    """
    # file_contents_additions
    file_additions = patch.get("file_contents_additions", {})
    if isinstance(file_additions, dict):
        existing_files = profile.setdefault("file_contents", {})
        for path, content in file_additions.items():
            if path not in existing_files:
                existing_files[path] = content

    # directory_tree_additions
    dir_additions = patch.get("directory_tree_additions", {})
    if isinstance(dir_additions, dict):
        existing_tree = profile.setdefault("directory_tree", {})
        for parent, entries in dir_additions.items():
            if not isinstance(entries, list):
                continue
            if parent in existing_tree:
                existing_names = {e.get("name") for e in existing_tree[parent]}
                for entry in entries:
                    if entry.get("name") not in existing_names:
                        existing_tree[parent].append(entry)
            else:
                existing_tree[parent] = entries

    # installed_packages_additions
    # Auto-coerce plain strings to {"name": str, "version": "latest"} dicts
    # so the schema validator doesn't reject them.
    pkg_additions = patch.get("installed_packages_additions", [])
    if isinstance(pkg_additions, list):
        existing_pkgs = profile.setdefault("installed_packages", [])
        # Match existing format: if existing packages are dicts, coerce strings
        uses_dicts = bool(existing_pkgs) and isinstance(existing_pkgs[0], dict)
        existing_names = _pkg_names(existing_pkgs)
        for pkg in pkg_additions:
            if isinstance(pkg, str) and uses_dicts:
                pkg = {"name": pkg, "version": "latest"}
            name = pkg.get("name", "") if isinstance(pkg, dict) else str(pkg)
            if name not in existing_names:
                existing_pkgs.append(pkg)
                existing_names.add(name)

    # users_additions
    user_additions = patch.get("users_additions", [])
    if isinstance(user_additions, list):
        existing_users = profile.setdefault("users", [])
        existing_names = {u.get("name") for u in existing_users}
        for user in user_additions:
            if user.get("name") not in existing_names:
                existing_users.append(user)

    # lure_chains — stored separately
    chains = patch.get("lure_chains", [])
    if not isinstance(chains, list):
        chains = []

    return profile, chains


def enrich_lures(profile: dict, max_retries: int = 2) -> tuple[dict, list]:
    """Main entry point — enrich a profile with extended lures and chains.

    Returns (enriched_profile, lure_chains).
    """
    gap_report = analyze_lure_gaps(profile)

    # Check if all 10 categories are already satisfied
    if all(info["satisfied"] for info in gap_report.values()):
        log.info("All lure categories satisfied — skipping enrichment.")
        return profile, []

    unsatisfied = [k for k, v in gap_report.items() if not v["satisfied"]]
    log.info("Lure gaps detected in: %s — running enrichment.", unsatisfied)

    backup = copy.deepcopy(profile)

    for attempt in range(1, max_retries + 1):
        try:
            prompt = _build_enrichment_prompt(profile, gap_report)
            llm_output = query_openai(prompt, temperature=0.8)

            json_str = extract_json(llm_output)
            if json_str is None:
                log.warning("Attempt %d: No JSON in LLM output.", attempt)
                continue

            patch = json.loads(json_str)
            profile, chains = _merge_patch(profile, patch)

            if validate_profile(profile):
                log.info("Lure enrichment succeeded on attempt %d.", attempt)
                return profile, chains

            # Validation failed — revert and retry
            log.warning("Attempt %d: Enriched profile failed validation, reverting.", attempt)
            profile = copy.deepcopy(backup)

        except (json.JSONDecodeError, TypeError, KeyError) as e:
            log.warning("Attempt %d: Error during enrichment: %s", attempt, e)
            profile = copy.deepcopy(backup)

    log.warning("Lure enrichment failed after %d attempts, returning original profile.", max_retries)
    return profile, []


def score_lure_realism(profile: dict) -> list[dict]:
    """Post-enrichment realism checks.

    Returns list of {"issue": str, "severity": "high"|"medium"|"low"}.
    """
    issues: list[dict] = []
    file_contents = profile.get("file_contents", {})
    # Build a joined string of all service names for substring matching
    # (e.g. "mysqld" contains "mysql", "postgresql-14" contains "postgresql")
    services_joined = " ".join(s.get("name", "").lower() for s in profile.get("services", []))
    packages = _pkg_names(profile.get("installed_packages", []))
    hosts_content = file_contents.get("/etc/hosts", "")

    def _has_service(*needles: str) -> bool:
        return any(n in services_joined for n in needles)

    # Collect all internal IPs mentioned in /etc/hosts
    from Reconfigurator.new_config_pipeline import _INTERNAL_IP_RE
    hosts_ips = set(_INTERNAL_IP_RE.findall(hosts_content))

    # Only flag service mismatches when credentials target localhost or the
    # local hostname — references to remote hosts in /etc/hosts are expected
    # (deployment configs, mail, logs, etc.)
    hostname = profile.get("system", {}).get("hostname", "")
    _local_refs = re.compile(
        r"localhost|127\.0\.0\.1|" + re.escape(hostname) if hostname else r"localhost|127\.0\.0\.1"
    )

    # Paths that are not credential/config files — skip service-mismatch checks
    _skip_svc_check = re.compile(r"/etc/hosts$|/var/mail/|/var/log/")

    for path, content in file_contents.items():
        # Credentials referencing LOCAL services not in the services list
        if not _skip_svc_check.search(path) and _local_refs.search(content):
            if re.search(r"mysql|mariadb", content, re.IGNORECASE) and not _has_service("mysql", "mariadb"):
                issues.append({
                    "issue": f"{path} references local MySQL/MariaDB but no such service exists",
                    "severity": "medium",
                })
            if re.search(r"postgres|psql|pgpass", content, re.IGNORECASE) and not _has_service("postgresql", "postgres", "pgbouncer"):
                issues.append({
                    "issue": f"{path} references local PostgreSQL but no such service exists",
                    "severity": "medium",
                })
            if re.search(r"redis", content, re.IGNORECASE) and not _has_service("redis"):
                issues.append({
                    "issue": f"{path} references local Redis but no such service exists",
                    "severity": "low",
                })

        # Internal IPs not in /etc/hosts (skip .0 network addresses from CIDR notation)
        file_ips = set(_INTERNAL_IP_RE.findall(content))
        file_ips = {ip for ip in file_ips if not ip.endswith(".0")}
        orphan_ips = file_ips - hosts_ips
        if orphan_ips and path != "/etc/hosts":
            issues.append({
                "issue": f"{path} references IPs {orphan_ips} not found in /etc/hosts",
                "severity": "medium",
            })

        # AWS credentials but no awscli package
        if _CLOUD_CRED_RE.search(content) and "awscli" not in packages and "aws-cli" not in packages:
            if re.search(r"aws_access_key|AKIA", content):
                issues.append({
                    "issue": f"{path} has AWS credentials but awscli is not installed",
                    "severity": "low",
                })

    return issues
