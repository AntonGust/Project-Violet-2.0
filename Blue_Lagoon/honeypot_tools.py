import json
import socket
import subprocess
import time
import os

from pathlib import Path
from typing import Any

import config as cfg

runid = os.environ.get("RUNID")
# Resolve honeypot API key: provider-specific env var takes precedence
from Utils.llm_client import _PROVIDER_ENV_KEYS
_hp_env_key = _PROVIDER_ENV_KEYS.get(cfg.llm_provider_hp, "OPENAI_API_KEY")
openai_key = os.environ.get(_hp_env_key) or os.environ.get("OPENAI_API_KEY")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COWRIE_JSON_LOG = PROJECT_ROOT / "cowrie_config" / "var" / "log" / "cowrie" / "cowrie.json"
OVERRIDE_FILE = PROJECT_ROOT / "docker-compose.override.yml"
HONEYNET_COMPOSE = PROJECT_ROOT / "docker-compose.honeynet.yml"

_file_offset = 0

# Per-hop file offsets for honeynet mode: {hop_index: offset}
_hop_offsets: dict[int, int] = {}


def _compose_env() -> dict:
    """Build the environment dict for docker-compose commands."""
    env = os.environ.copy()
    env.update({
        "RUNID": runid,
        "OPENAI_API_KEY": openai_key or "",
    })

    # Inject DB env vars from db_config.json if present.
    # These are referenced in docker-compose.yml via ${COWRIE_DB_*:-} substitution
    # so Cowrie's container receives them.  The honeypot-db service uses its own
    # env block in the override file.
    db_config_path = PROJECT_ROOT / "cowrie_config" / "db_config.json"
    if db_config_path.exists():
        try:
            with open(db_config_path) as f:
                db_config = json.load(f)
            ip_suffix = db_config.get("ip_suffix", "0.4")
            env["COWRIE_DB_HOST"] = f"172.{runid}.{ip_suffix}"
            env["COWRIE_DB_ENGINE"] = db_config.get("engine", "")
            env["COWRIE_DB_PORT"] = str(db_config.get("port", ""))
            env["COWRIE_DB_ROOT_PASSWORD"] = db_config.get("root_password", "")
            # Use first database/user as primary
            dbs = db_config.get("databases", [])
            if dbs:
                env["COWRIE_DB_NAME"] = dbs[0].get("name", "")
                users = dbs[0].get("users", [])
                if users:
                    env["COWRIE_DB_USER"] = users[0].get("username", "")
                    env["COWRIE_DB_PASSWORD"] = users[0].get("password", "")
        except (json.JSONDecodeError, OSError):
            pass

    return env


def _compose_files() -> list[str]:
    """Return the list of compose file flags, including override if it exists."""
    if cfg.honeynet_enabled and HONEYNET_COMPOSE.exists():
        return ["-f", "docker-compose.honeynet.yml"]
    files = ["-f", "docker-compose.yml"]
    if OVERRIDE_FILE.exists():
        files.extend(["-f", "docker-compose.override.yml"])
    return files


def generate_db_compose(db_config: dict[str, Any], cowrie_base: Path) -> None:
    """
    Write docker-compose.override.yml with the honeypot-db service.

    Uses a fixed image (mysql:8.0 or postgres:16) regardless of the profile's
    spoofed version. The version string is spoofed via the LLM layer.
    """
    engine = db_config["engine"]
    image = db_config["image"]
    root_password = db_config["root_password"]
    ip_suffix = "0.4"

    if engine == "mysql":
        env_block = (
            f"      MYSQL_ROOT_PASSWORD: \"{root_password}\"\n"
        )
        # Create users/dbs via init SQL, not env vars
        for db in db_config.get("databases", []):
            env_block += f"      MYSQL_DATABASE: \"{db['name']}\"\n"
            break  # Only first DB via env var; rest via init SQL
        healthcheck = (
            '    healthcheck:\n'
            '      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]\n'
            '      interval: 5s\n'
            '      timeout: 3s\n'
            '      retries: 15\n'
        )
        log_volume = "./cowrie_config/var/log/db:/var/log/mysql"
    else:
        env_block = (
            f"      POSTGRES_PASSWORD: \"{root_password}\"\n"
        )
        for db in db_config.get("databases", []):
            if db["name"] != "postgres":
                env_block += f"      POSTGRES_DB: \"{db['name']}\"\n"
                break
        healthcheck = (
            '    healthcheck:\n'
            '      test: ["CMD-SHELL", "pg_isready -U postgres"]\n'
            '      interval: 5s\n'
            '      timeout: 3s\n'
            '      retries: 15\n'
        )
        log_volume = "./cowrie_config/var/log/db:/var/log/postgresql"

    # Only the honeypot-db service goes in the override.
    # Cowrie's COWRIE_DB_* env vars are passed via _compose_env() and
    # referenced in the base docker-compose.yml with ${COWRIE_DB_*:-} defaults.
    override_content = (
        f'services:\n'
        f'  honeypot-db:\n'
        f'    image: "{image}"\n'
        f'    restart: "no"\n'
        f'    environment:\n'
        f'{env_block}'
        f'    volumes:\n'
        f'      - "./cowrie_config/db_init:/docker-entrypoint-initdb.d:ro"\n'
        f'      - "{log_volume}"\n'
        f'    networks:\n'
        f'      innet:\n'
        f'        ipv4_address: "172.${{RUNID}}.{ip_suffix}"\n'
        f'{healthcheck}'
    )

    OVERRIDE_FILE.write_text(override_content, encoding="utf-8")
    print(f"Generated docker-compose.override.yml ({engine}, image={image})")


def remove_db_compose() -> None:
    """Delete the override file if it exists."""
    if OVERRIDE_FILE.exists():
        OVERRIDE_FILE.unlink()
        print("Removed docker-compose.override.yml")


def wait_for_db(timeout: int = 60) -> None:
    """Wait for honeypot-db container health check to pass."""
    if not OVERRIDE_FILE.exists():
        return  # No DB configured

    container_name = _resolve_container_name("honeypot-db")
    start = time.time()
    while time.time() - start < timeout:
        # Check if container is still running
        running = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True, text=True,
        )
        if running.stdout.strip() == "false":
            print(f"Warning: Honeypot DB container exited — check 'docker logs {container_name}'")
            return

        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
            capture_output=True, text=True,
        )
        status = result.stdout.strip()
        if status == "healthy":
            print("Honeypot DB is ready (healthy)")
            return
        time.sleep(2)
    print(f"Warning: Honeypot DB did not become healthy within {timeout}s")


def start_dockers():
    print("Starting Docker containers...")

    env = _compose_env()
    compose_files = _compose_files()

    # Tear down any stale containers first.  docker-compose 1.29.2 crashes
    # with 'ContainerConfig' KeyError when trying to *recreate* a container
    # whose old image metadata is incomplete.  A clean down+up avoids this.
    subprocess.run(
        ["docker-compose"] + compose_files + ["-p", runid, "down", "--remove-orphans"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Also tear down networks from the default project name (directory-based)
    # to avoid subnet overlap when the same compose file was previously run
    # without an explicit -p flag.
    subprocess.run(
        ["docker", "compose"] + compose_files + ["down", "--remove-orphans"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        ["docker-compose"] + compose_files + ["-p", runid, "build"],
        check=True,
        env=env,
    )
    subprocess.run(
        ["docker-compose"] + compose_files + ["-p", runid, "up", "-d"],
        check=True,
        env=env,
    )
    print("Docker containers started")


def stop_dockers():
    print("Stopping Docker containers...")

    env = _compose_env()
    compose_files = _compose_files()

    subprocess.run(
        ["docker-compose"] + compose_files + ["-p", runid, "down"],
        check=True,
        env=env,
    )
    print("Docker containers stopped")

    subprocess.run(
        ["docker", "image", "prune", "-f"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def get_new_hp_logs(since: str | None = None, hop_index: int = 0) -> list[dict]:
    """
    Read new Cowrie JSON events from the host-mounted log file.
    Tracks byte offset between calls so only new lines are returned.

    Args:
        since: Unused, kept for API compatibility.
        hop_index: Which hop's logs to read (0-based). Only used when honeynet_enabled.

    Returns:
        List of event dicts in the format expected by extract_session():
        [{"level": "info", "status": "Interaction", "event": {...}}, ...]
    """
    global _file_offset, _hop_offsets

    log_path = get_cowrie_log_path(hop_index) if cfg.honeynet_enabled else COWRIE_JSON_LOG

    if not log_path.exists():
        return []

    # Select the right offset tracker
    if cfg.honeynet_enabled:
        offset = _hop_offsets.get(hop_index, 0)
    else:
        offset = _file_offset

    file_size = log_path.stat().st_size
    if file_size < offset:
        offset = 0

    if file_size == offset:
        return []

    events = []

    with open(log_path, "r") as f:
        f.seek(offset)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_id = event.get("eventid", "")

            # Only collect cowrie.command.input events.  Cowrie also fires
            # cowrie.command.failed for LLM-handled commands, but it strips
            # quotes so the input text differs and string dedup fails.
            # Since every failed command already has a preceding input
            # event, we safely ignore failed events entirely.
            if event_id != "cowrie.command.input":
                continue

            cmd = event.get("input", "")
            events.append({
                "level": "info",
                "status": "Interaction",
                "event": {
                    "Protocol": "SSH",
                    "Command": cmd,
                    "CommandOutput": "",
                    "User": event.get("username", "root"),
                    "Timestamp": event.get("timestamp", ""),
                },
            })

        new_offset = f.tell()

    # Store the updated offset
    if cfg.honeynet_enabled:
        _hop_offsets[hop_index] = new_offset
    else:
        _file_offset = new_offset

    return events


def get_cowrie_log_path(hop_index: int = 0) -> Path:
    """Return the path to a specific hop's Cowrie JSON log file."""
    if cfg.honeynet_enabled:
        return PROJECT_ROOT / f"cowrie_config_hop{hop_index + 1}" / "var" / "log" / "cowrie" / "cowrie.json"
    return COWRIE_JSON_LOG


def clear_hp_logs():
    """Reset the log offset so old events aren't re-processed.

    If the log file is writable, truncate it.  Otherwise just skip to EOF
    so that subsequent reads only return new events.

    When honeynet_enabled, clears logs for all hops.
    """
    global _file_offset, _hop_offsets

    if cfg.honeynet_enabled:
        for i in range(len(cfg.chain_profiles)):
            log_path = get_cowrie_log_path(i)
            _hop_offsets[i] = 0
            if log_path.exists():
                try:
                    log_path.write_text("")
                    print(f"Cowrie hop{i + 1} JSON log truncated")
                except PermissionError:
                    _hop_offsets[i] = log_path.stat().st_size
                    print(f"Cowrie hop{i + 1} log not writable, skipping to offset {_hop_offsets[i]}")
            # Clear LLM token log for this hop
            token_log = log_path.parent.parent.parent / "llm_tokens.jsonl"
            if token_log.exists():
                try:
                    token_log.write_text("")
                except PermissionError:
                    pass
        _file_offset = 0
        return

    if COWRIE_JSON_LOG.exists():
        try:
            COWRIE_JSON_LOG.write_text("")
            _file_offset = 0
            print("Cowrie JSON log truncated")
        except PermissionError:
            _file_offset = COWRIE_JSON_LOG.stat().st_size
            print(f"Cowrie JSON log not writable, skipping to offset {_file_offset}")
    else:
        _file_offset = 0
        print("Cowrie JSON log does not exist yet, offset reset")
    # Clear LLM token log
    token_log = COWRIE_JSON_LOG.parent.parent.parent / "llm_tokens.jsonl"
    if token_log.exists():
        try:
            token_log.write_text("")
        except PermissionError:
            pass


def _resolve_container_name(service: str) -> str:
    """Find the actual container name for a compose service.

    docker-compose v1 uses underscores (``10_cowrie_1``),
    v2 uses hyphens (``10-cowrie-1``).  Try both conventions.
    """
    for sep in ("_", "-"):
        name = f"{runid}{sep}{service}{sep}1"
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}}", name],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return name
    # Fallback — v2 convention
    return f"{runid}-{service}-1"


def stop_single_hop(hop_index: int) -> None:
    """Stop a single hop's Cowrie container without tearing down the whole stack."""
    service_name = f"cowrie_hop{hop_index + 1}"
    container_name = _resolve_container_name(service_name)
    subprocess.run(
        ["docker", "stop", container_name],
        capture_output=True,
    )
    print(f"Stopped {service_name}")


def start_single_hop(hop_index: int) -> None:
    """Start a single hop's Cowrie container."""
    service_name = f"cowrie_hop{hop_index + 1}"
    container_name = _resolve_container_name(service_name)
    subprocess.run(
        ["docker", "start", container_name],
        capture_output=True,
    )
    print(f"Started {service_name}")
    wait_for_cowrie(service_name)


def wait_for_cowrie(service_name: str = "cowrie", timeout: int = 60):
    """Wait until Cowrie is ready to accept SSH connections.

    Cowrie's port 2222 is only on the Docker internal network (not
    mapped to the host), so we check readiness by looking for the
    "listening on 2222" line in container logs.
    """
    container_name = _resolve_container_name(service_name)
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            ["docker", "logs", container_name],
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        if "Ready to accept SSH connections" in combined:
            print(f"Cowrie ({service_name}) is ready (SSH listener started)")
            return
        time.sleep(2)
    print(f"Warning: Cowrie ({service_name}) did not become ready within {timeout}s")


def wait_for_all_cowrie(chain_length: int, timeout: int = 90):
    """Wait for all Cowrie instances in the honeynet chain to be ready."""
    for i in range(chain_length):
        wait_for_cowrie(f"cowrie_hop{i + 1}", timeout=timeout)


def wait_for_honeynet_dbs(db_enabled_flags: list[bool], timeout: int = 60) -> None:
    """Wait for all DB containers in the honeynet chain to become healthy."""
    for i, enabled in enumerate(db_enabled_flags):
        if not enabled:
            continue
        service = f"honeypot_db_hop{i + 1}"
        container_name = _resolve_container_name(service)
        print(f"Waiting for {service}...")
        start = time.time()
        while time.time() - start < timeout:
            running = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
                capture_output=True, text=True,
            )
            if running.stdout.strip() == "false":
                print(f"Warning: {service} container exited — check 'docker logs {container_name}'")
                break

            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Health.Status}}", container_name],
                capture_output=True, text=True,
            )
            status = result.stdout.strip()
            if status == "healthy":
                print(f"{service} is ready (healthy)")
                break
            time.sleep(2)
        else:
            print(f"Warning: {service} did not become healthy within {timeout}s")


# If you need to call these functions directly
if __name__ == "__main__":
    start_dockers()
    # or stop_dockers()
