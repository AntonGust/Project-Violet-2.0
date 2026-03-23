"""Canary URL generation for LLM attacker detection.

Plants honey URLs in profile files (.bash_history, READMEs, config comments,
cron scripts). If the attacker fetches them via curl/wget, it confirms
automated behavior — a human would inspect the URL first.
"""

import random
import uuid


def _random_id() -> str:
    return f"cu-{uuid.uuid4().hex[:8]}"


# Realistic-looking internal URL templates
_URL_TEMPLATES = [
    "http://internal-deploy.{domain}/scripts/setup.sh",
    "http://infra.{domain}/releases/latest/install.sh",
    "http://tools.{domain}/monitoring/agent-install.sh",
    "http://repo.{domain}/packages/bootstrap.sh",
    "http://automation.{domain}/deploy/update-node.sh",
    "http://ci.{domain}/artifacts/build-tools.sh",
    "http://registry.{domain}/config/pull-secrets.sh",
    "http://backup.{domain}/restore/recover.sh",
]

# Context lines that make the URL look natural in different file types
_BASH_HISTORY_CONTEXTS = [
    "curl -sSL {url} | bash",
    "wget -qO- {url} | sudo bash",
    "curl -fsSL {url} -o /tmp/setup.sh && bash /tmp/setup.sh",
]

_README_CONTEXTS = [
    "# Quick setup: curl -sSL {url} | bash",
    "## Installation\n\nDownload and run the setup script:\n```\ncurl -sSL {url} | bash\n```",
    "For automated deployment, run: `wget -qO- {url} | bash`",
]

_CONFIG_CONTEXTS = [
    "# Auto-update script: {url}",
    "# Source: {url}",
    "# Provisioning endpoint: {url}",
]

_CRON_CONTEXTS = [
    "0 3 * * * curl -sSL {url} | bash  # nightly update",
    "*/30 * * * * wget -qO /dev/null {url}  # health check",
]


def _pick_domain(profile: dict) -> str:
    """Derive a plausible internal domain from the profile."""
    hostname = profile.get("system", {}).get("hostname", "srv01")
    # Use hostname-derived domain or a generic one
    candidates = [
        f"{hostname}.internal",
        "ops.internal",
        "infra.corp.local",
        "deploy.internal",
    ]
    return random.choice(candidates)


def generate_canary_lures(profile: dict, num_lures: int = 3) -> list[dict]:
    """Generate honey URLs to plant in profile files.

    Returns list of:
        {
            "url": str,
            "context_line": str,      # The line to insert into the file
            "file_path": str,         # Where to plant it
            "plant_type": str,        # bash_history | readme | config | cron
            "token_id": str,
        }
    """
    domain = _pick_domain(profile)
    file_contents = profile.get("file_contents", {})
    users = profile.get("users", [])

    # Collect candidate plant locations
    candidates = []

    # .bash_history files
    for user in users:
        home = user.get("home", f"/home/{user['name']}")
        history_path = f"{home}/.bash_history"
        candidates.append(("bash_history", history_path))

    # README / doc files
    for path in file_contents:
        lower = path.lower()
        if any(x in lower for x in ("readme", "doc", "notes", "todo")):
            candidates.append(("readme", path))

    # Config files with comments
    for path in file_contents:
        if any(path.endswith(ext) for ext in (".conf", ".cfg", ".ini", ".yml", ".yaml", ".env")):
            candidates.append(("config", path))

    # Cron files
    for path in file_contents:
        if "cron" in path.lower():
            candidates.append(("cron", path))

    # Always ensure at least a .bash_history target
    if not candidates:
        candidates.append(("bash_history", "/root/.bash_history"))

    # Generate lures
    lures = []
    used_urls = set()
    templates = list(_URL_TEMPLATES)
    random.shuffle(templates)
    random.shuffle(candidates)

    for i in range(min(num_lures, len(templates))):
        url = templates[i].format(domain=domain)
        if url in used_urls:
            continue
        used_urls.add(url)

        plant_type, file_path = candidates[i % len(candidates)]

        if plant_type == "bash_history":
            context = random.choice(_BASH_HISTORY_CONTEXTS).format(url=url)
        elif plant_type == "readme":
            context = random.choice(_README_CONTEXTS).format(url=url)
        elif plant_type == "config":
            context = random.choice(_CONFIG_CONTEXTS).format(url=url)
        elif plant_type == "cron":
            context = random.choice(_CRON_CONTEXTS).format(url=url)
        else:
            context = f"# {url}"

        lures.append({
            "url": url,
            "context_line": context,
            "file_path": file_path,
            "plant_type": plant_type,
            "token_id": _random_id(),
        })

    return lures


def apply_canary_urls_to_profile(profile: dict, num_lures: int = 3) -> tuple[dict, list[dict]]:
    """Generate canary URLs and inject them into the profile's file_contents.

    Returns (modified_profile, list_of_planted_canaries).
    Each planted canary dict includes: token_id, url, planted_in.
    """
    lures = generate_canary_lures(profile, num_lures)
    file_contents = profile.setdefault("file_contents", {})

    planted = []
    for lure in lures:
        path = lure["file_path"]
        context = lure["context_line"]

        if path in file_contents:
            # Append to existing file
            file_contents[path] = file_contents[path].rstrip("\n") + "\n" + context + "\n"
        else:
            # Create new file with the context
            file_contents[path] = context + "\n"

        planted.append({
            "token_id": lure["token_id"],
            "url": lure["url"],
            "planted_in": path,
            "plant_type": lure["plant_type"],
        })

    return profile, planted
