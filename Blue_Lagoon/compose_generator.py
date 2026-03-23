"""Generate docker-compose.honeynet.yml for multi-hop HoneyNet deployments.

Creates isolated Docker bridge networks so that:
- Kali sits only on net_entry and can only reach Pot1
- Each pot sits on two networks (inbound + outbound), except the last pot (inbound only)
- DB containers for applicable hops sit on the same network as their pot
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from Blue_Lagoon.credential_chain import ChainManifest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def generate_honeynet_compose(manifest: "ChainManifest") -> Path:
    """Build and write docker-compose.honeynet.yml from the chain manifest.

    Returns the path to the generated file.
    """
    run_id = manifest.run_id
    hops = manifest.hops
    num_hops = len(hops)

    services: dict = {}
    networks: dict = {}

    # --- Networks ---
    # net_entry: Kali <-> Pot1
    networks["net_entry"] = {
        "driver": "bridge",
        "ipam": {"config": [{"subnet": f"172.{run_id}.0.0/24"}]},
    }
    # net_hopN: PotN <-> PotN+1
    for i in range(num_hops - 1):
        net_name = f"net_hop{i + 1}"
        networks[net_name] = {
            "driver": "bridge",
            "ipam": {"config": [{"subnet": f"172.{run_id}.{i + 1}.0/24"}]},
        }

    # --- Kali ---
    services["kali"] = {
        "build": "Blue_Lagoon/kali_image",
        "privileged": True,
        "ports": [f"30{run_id}:3022"],
        "networks": {
            "net_entry": {"ipv4_address": f"172.{run_id}.0.2"},
        },
    }

    # --- Cowrie pots ---
    for i, hop in enumerate(hops):
        hop_num = i + 1
        service_name = f"cowrie_hop{hop_num}"
        svc: dict = {
            "build": "Cowrie/cowrie-src",
            "restart": "always",
            "extra_hosts": ["host.docker.internal:host-gateway"],
            "environment": [
                f"COWRIE_HYBRID_LLM_API_KEY=${{OPENAI_API_KEY}}",
                "COWRIE_HYBRID_LLM_ENABLED=true",
                "HONEYNET_MODE=true",
            ],
            "volumes": [
                f"./cowrie_config_hop{hop_num}/etc:/cowrie/cowrie-git/etc",
                f"./cowrie_config_hop{hop_num}/honeyfs:/cowrie/cowrie-git/honeyfs",
                f"./cowrie_config_hop{hop_num}/share:/cowrie/cowrie-git/share/cowrie",
                f"./cowrie_config_hop{hop_num}/var:/cowrie/cowrie-git/var",
            ],
            "networks": {},
        }

        # Entry pot gets exposed port for demo mode
        if i == 0:
            svc["ports"] = [f"22{run_id}:2222"]

        # Inbound network
        if i == 0:
            # First pot: on net_entry
            svc["networks"]["net_entry"] = {
                "ipv4_address": f"172.{run_id}.0.10",
            }
        else:
            # Inner pots: on net_hop{i} (shared with predecessor)
            net_in = f"net_hop{i}"
            svc["networks"][net_in] = {
                "ipv4_address": f"172.{run_id}.{i}.{10 + i}",
            }

        # Outbound network (all but last pot)
        if i < num_hops - 1:
            net_out = f"net_hop{i + 1}"
            svc["networks"][net_out] = {
                "ipv4_address": f"172.{run_id}.{i + 1}.{10 + i}",
            }

        # DB env vars for hops with databases
        _inject_db_env(svc, hop_num, i, run_id)

        services[service_name] = svc

    # --- DB containers (per-hop, only where enabled) ---
    import config as cfg
    for i, hop in enumerate(hops):
        hop_num = i + 1
        if i < len(cfg.chain_db_enabled) and cfg.chain_db_enabled[i]:
            db_svc = _build_db_service(hop_num, i, run_id)
            if db_svc:
                services[f"honeypot_db_hop{hop_num}"] = db_svc

    compose = {"services": services, "networks": networks}

    out_path = PROJECT_ROOT / "docker-compose.honeynet.yml"
    with open(out_path, "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False)

    print(f"Generated {out_path.name} ({num_hops} hops)")
    return out_path


def _inject_db_env(svc: dict, hop_num: int, hop_index: int, run_id: str) -> None:
    """Add COWRIE_DB_* env vars to a pot service if its db_config.json exists."""
    db_config_path = PROJECT_ROOT / f"cowrie_config_hop{hop_num}" / "db_config.json"
    if not db_config_path.exists():
        # Add empty defaults so Cowrie doesn't complain
        for var in ["COWRIE_DB_HOST", "COWRIE_DB_ENGINE", "COWRIE_DB_PORT",
                     "COWRIE_DB_NAME", "COWRIE_DB_USER", "COWRIE_DB_PASSWORD",
                     "COWRIE_DB_ROOT_PASSWORD"]:
            svc["environment"].append(f"{var}=")
        return

    try:
        with open(db_config_path) as f:
            db_config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    # Compute DB host IP to match _build_db_service() IP assignment
    if hop_index == 0:
        db_ip = f"172.{run_id}.0.{20 + hop_num}"
    else:
        db_ip = f"172.{run_id}.{hop_index}.{20 + hop_num}"
    svc["environment"].append(f"COWRIE_DB_HOST={db_ip}")
    svc["environment"].append(f"COWRIE_DB_ENGINE={db_config.get('engine', '')}")
    svc["environment"].append(f"COWRIE_DB_PORT={db_config.get('port', '')}")
    svc["environment"].append(f"COWRIE_DB_ROOT_PASSWORD={db_config.get('root_password', '')}")
    dbs = db_config.get("databases", [])
    if dbs:
        svc["environment"].append(f"COWRIE_DB_NAME={dbs[0].get('name', '')}")
        users = dbs[0].get("users", [])
        if users:
            svc["environment"].append(f"COWRIE_DB_USER={users[0].get('username', '')}")
            svc["environment"].append(f"COWRIE_DB_PASSWORD={users[0].get('password', '')}")


def _build_db_service(hop_num: int, hop_index: int, run_id: str) -> dict | None:
    """Build a DB service dict for a specific hop, if db_config.json exists."""
    db_config_path = PROJECT_ROOT / f"cowrie_config_hop{hop_num}" / "db_config.json"
    if not db_config_path.exists():
        return None

    try:
        with open(db_config_path) as f:
            db_config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    engine = db_config["engine"]
    image = db_config["image"]
    root_password = db_config["root_password"]

    # DB sits on the same inbound network as its pot
    if hop_index == 0:
        net_name = "net_entry"
        ip = f"172.{run_id}.0.{20 + hop_num}"
    else:
        net_name = f"net_hop{hop_index}"
        ip = f"172.{run_id}.{hop_index}.{20 + hop_num}"

    svc: dict = {
        "image": image,
        "restart": "no",
        "volumes": [
            f"./cowrie_config_hop{hop_num}/db_init:/docker-entrypoint-initdb.d:ro",
            f"./cowrie_config_hop{hop_num}/var/log/db:/var/log/{'mysql' if engine == 'mysql' else 'postgresql'}",
        ],
        "networks": {
            net_name: {"ipv4_address": ip},
        },
    }

    if engine == "mysql":
        env = {"MYSQL_ROOT_PASSWORD": root_password}
        dbs = db_config.get("databases", [])
        if dbs:
            env["MYSQL_DATABASE"] = dbs[0]["name"]
        svc["environment"] = env
        svc["healthcheck"] = {
            "test": ["CMD", "mysqladmin", "ping", "-h", "localhost"],
            "interval": "5s",
            "timeout": "3s",
            "retries": 15,
        }
    else:
        env = {"POSTGRES_PASSWORD": root_password}
        dbs = db_config.get("databases", [])
        for db in dbs:
            if db["name"] != "postgres":
                env["POSTGRES_DB"] = db["name"]
                break
        svc["environment"] = env
        svc["healthcheck"] = {
            "test": ["CMD-SHELL", "pg_isready -U postgres"],
            "interval": "5s",
            "timeout": "3s",
            "retries": 15,
        }

    return svc
