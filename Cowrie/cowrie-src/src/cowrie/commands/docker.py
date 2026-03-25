"""
Native docker command handler for Cowrie honeypot.

Handles the most common read-only subcommands (ps, images, logs, inspect)
with deterministic output from the profile. Mutating commands (exec, run,
build) fall through to LLM fallback via self.exit() with no output.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.fs import FileNotFound

commands = {}

# Map common service names to Docker images
_SERVICE_IMAGES: dict[str, str] = {
    "nginx": "nginx:1.25-alpine",
    "apache2": "httpd:2.4",
    "mysql": "mysql:8.0",
    "mysqld": "mysql:8.0",
    "postgres": "postgres:16-alpine",
    "redis": "redis:7-alpine",
    "grafana": "grafana/grafana:10.2.3",
    "prometheus": "prom/prometheus:v2.48.1",
    "node_exporter": "prom/node-exporter:v1.7.0",
    "alertmanager": "prom/alertmanager:v0.26.0",
    "mosquitto": "eclipse-mosquitto:2.0",
    "gitea": "gitea/gitea:1.21",
    "jenkins": "jenkins/jenkins:lts",
    "traefik": "traefik:v2.10",
    "portainer": "portainer/portainer-ce:2.19",
    "registry": "registry:2",
}


class Command_docker(HoneyPotCommand):
    def _get_profile(self) -> dict:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return {}
        return getattr(handler, "_profile", {})

    def _get_containers(self) -> list[dict[str, Any]]:
        """Build container list from profile docker-compose files and services."""
        profile = self._get_profile()
        containers = []

        # Parse docker-compose files from profile
        for path, content in profile.get("file_contents", {}).items():
            if "docker-compose" in path or "docker_compose" in path:
                for m in re.finditer(r"^\s{2}(\w[\w-]+):\s*$", content, re.MULTILINE):
                    name = m.group(1)
                    # Try to find image in the section
                    section = content[m.end():m.end() + 500]
                    img_match = re.search(r"image:\s*(\S+)", section)
                    image = img_match.group(1) if img_match else _SERVICE_IMAGES.get(name, f"{name}:latest")
                    # Find ports
                    ports_list = re.findall(r'"?(\d+:\d+)"?', section[:300])
                    ports_str = ", ".join(f"0.0.0.0:{p.split(':')[0]}->{p.split(':')[1]}/tcp" for p in ports_list[:3])
                    containers.append({
                        "name": name,
                        "image": image,
                        "ports": ports_str,
                    })

        # If no compose files, derive from services that look container-ish
        if not containers:
            for svc in profile.get("services", []):
                svc_name = svc["name"].split("-")[0]
                if svc_name in _SERVICE_IMAGES:
                    port_strs = []
                    for p in svc.get("ports", []):
                        port_strs.append(f"0.0.0.0:{p}->{p}/tcp")
                    containers.append({
                        "name": svc_name,
                        "image": _SERVICE_IMAGES[svc_name],
                        "ports": ", ".join(port_strs),
                    })

        return containers

    def _container_id(self, name: str) -> str:
        """Generate a deterministic 12-char container ID from name."""
        return hashlib.md5(name.encode()).hexdigest()[:12]

    def call(self) -> None:
        if not self.args:
            self._show_usage()
            return

        # Handle `docker compose` (new style) as alias
        args = list(self.args)
        if args[0] == "compose":
            args[0] = "compose"
            if len(args) > 1:
                subcmd = args[1]
                if subcmd == "ps":
                    self._do_ps(all_containers=False)
                    return
                elif subcmd == "logs":
                    target = args[2] if len(args) > 2 else None
                    self._do_logs(target)
                    return
            # Other compose subcommands → let LLM handle
            self._fallback()
            return

        subcmd = args[0]

        if subcmd == "ps":
            show_all = "-a" in args
            self._do_ps(all_containers=show_all)
        elif subcmd == "images":
            self._do_images()
        elif subcmd == "logs":
            target = args[1] if len(args) > 1 else None
            self._do_logs(target)
        elif subcmd == "inspect":
            target = args[1] if len(args) > 1 else None
            self._do_inspect(target)
        elif subcmd == "version":
            self._do_version()
        elif subcmd == "info":
            self._do_info()
        elif subcmd in ("node", "service", "stack", "secret", "network"):
            self._do_swarm(args)
        elif subcmd == "login":
            self._do_login(args[1:])
        elif subcmd in ("--help", "-h", "help"):
            self._show_usage()
        else:
            # exec, run, build, pull, push, etc. → LLM fallback
            self._fallback()

    def _fallback(self) -> None:
        """Exit without output so LLM fallback handles the command."""
        # Don't write anything — honeypot.py will detect no output and try LLM
        pass

    def _do_ps(self, all_containers: bool = False) -> None:
        containers = self._get_containers()
        if not containers:
            self.write("CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES\n")
            return

        self.write("CONTAINER ID   IMAGE                            COMMAND                  CREATED       STATUS        PORTS                    NAMES\n")
        for ct in containers:
            cid = self._container_id(ct["name"])
            image = ct.get("image", "unknown")
            ports = ct.get("ports", "")
            cmd_str = f'"/docker-entryp…"'
            self.write(
                f"{cid}   {image:<32s} {cmd_str:<24s} 47 days ago   Up 47 days   {ports:<24s} {ct['name']}\n"
            )

    def _do_images(self) -> None:
        containers = self._get_containers()
        seen = set()
        self.write("REPOSITORY                       TAG       IMAGE ID       CREATED        SIZE\n")
        for ct in containers:
            image = ct.get("image", "unknown:latest")
            if image in seen:
                continue
            seen.add(image)
            if ":" in image:
                repo, tag = image.rsplit(":", 1)
            else:
                repo, tag = image, "latest"
            img_id = hashlib.md5(image.encode()).hexdigest()[:12]
            self.write(f"{repo:<32s} {tag:<9s} {img_id}   2 months ago   {50 + len(image) * 3}MB\n")

    def _do_logs(self, target: str | None) -> None:
        if not target:
            self.write("\"docker logs\" requires exactly 1 argument.\n")
            return
        containers = self._get_containers()
        ct = None
        for c in containers:
            if c["name"] == target or self._container_id(c["name"]).startswith(target):
                ct = c
                break
        if not ct:
            self.write(f"Error: No such container: {target}\n")
            return
        # Try to read log files from honeyfs
        svc_name = ct["name"].split("-")[0]
        from cowrie.commands.journalctl import _SERVICE_LOG_MAP
        for log_path in _SERVICE_LOG_MAP.get(svc_name, []):
            try:
                resolved = self.fs.resolve_path(log_path, "/")
                contents = self.fs.file_contents(resolved)
                text = contents.decode("utf-8", errors="replace").strip()
                if text:
                    for line in text.split("\n")[-20:]:
                        self.write(line + "\n")
                    return
            except (FileNotFound, FileNotFoundError, Exception):
                continue
        # Generic log output
        self.write(f"Starting {ct['name']}...\n")
        self.write(f"{ct['name']} started successfully.\n")

    def _do_inspect(self, target: str | None) -> None:
        if not target:
            self.write("\"docker inspect\" requires at least 1 argument.\n")
            return
        containers = self._get_containers()
        ct = None
        for c in containers:
            if c["name"] == target or self._container_id(c["name"]).startswith(target):
                ct = c
                break
        if not ct:
            self.write(f"Error: No such object: {target}\n")
            return
        cid_full = hashlib.md5(ct["name"].encode()).hexdigest()
        image = ct.get("image", "unknown:latest")
        inspect_data = [{
            "Id": cid_full,
            "Created": "2026-01-27T08:00:00.000000000Z",
            "State": {"Status": "running", "Running": True, "Pid": 1234, "StartedAt": "2026-01-27T08:00:01.000000000Z"},
            "Name": f"/{ct['name']}",
            "Image": f"sha256:{hashlib.sha256(image.encode()).hexdigest()}",
            "Config": {"Image": image, "Hostname": ct["name"][:12]},
            "NetworkSettings": {
                "IPAddress": "172.17.0.2",
                "Ports": {},
            },
        }]
        self.write(json.dumps(inspect_data, indent=4) + "\n")

    def _do_login(self, args: list[str]) -> None:
        """Handle docker login — always report success."""
        registry = ""
        for a in args:
            if not a.startswith("-"):
                registry = a
                break
        if not registry:
            registry = "https://index.docker.io/v1/"
        self.write(f"WARNING! Using --password via the CLI is insecure. Use --password-stdin.\n")
        self.write(f"Login Succeeded\n")

    def _do_version(self) -> None:
        self.write("Client: Docker Engine - Community\n")
        self.write(" Version:           24.0.7\n")
        self.write(" API version:       1.43\n")
        self.write(" Go version:        go1.20.10\n")
        self.write(" Built:             Thu Oct 26 09:07:41 2023\n")
        self.write(" OS/Arch:           linux/amd64\n\n")
        self.write("Server: Docker Engine - Community\n")
        self.write(" Engine:\n")
        self.write("  Version:          24.0.7\n")
        self.write("  API version:      1.43 (minimum version 1.12)\n")
        self.write("  Go version:       go1.20.10\n")

    def _do_info(self) -> None:
        containers = self._get_containers()
        self.write(f"Containers: {len(containers)}\n")
        self.write(f" Running: {len(containers)}\n")
        self.write(" Paused: 0\n")
        self.write(" Stopped: 0\n")
        self.write(f"Images: {len(set(c.get('image', '') for c in containers))}\n")
        self.write("Server Version: 24.0.7\n")
        self.write("Storage Driver: overlay2\n")
        self.write(f"Operating System: {self.protocol.hostname}\n")
        self.write("Architecture: x86_64\n")
        self.write("CPUs: 4\n")
        self.write("Total Memory: 7.775GiB\n")

    def _do_swarm(self, args: list[str]) -> None:
        subcmd = args[0]
        sub2 = args[1] if len(args) > 1 else ""

        if subcmd == "node" and sub2 == "ls":
            hostname = self.protocol.hostname
            self.write("ID                            HOSTNAME     STATUS    AVAILABILITY   MANAGER STATUS   ENGINE VERSION\n")
            node_id = hashlib.md5(hostname.encode()).hexdigest()[:25]
            self.write(f"{node_id} *   {hostname:<12s} Ready     Active         Leader           24.0.7\n")
        elif subcmd == "service" and sub2 == "ls":
            containers = self._get_containers()
            self.write("ID             NAME           MODE         REPLICAS   IMAGE                    PORTS\n")
            for ct in containers:
                sid = self._container_id(ct["name"] + "_svc")
                image = ct.get("image", "unknown")
                ports = ct.get("ports", "")
                self.write(f"{sid}   {ct['name']:<14s} replicated   1/1        {image:<24s} {ports}\n")
        elif subcmd == "network" and sub2 == "ls":
            self.write("NETWORK ID     NAME              DRIVER    SCOPE\n")
            self.write(f"{self._container_id('bridge')}   bridge            bridge    local\n")
            self.write(f"{self._container_id('host')}   host              host      local\n")
            self.write(f"{self._container_id('none')}   none              null      local\n")
        else:
            # Other swarm commands → LLM fallback
            self._fallback()

    def _show_usage(self) -> None:
        self.write("Usage:  docker [OPTIONS] COMMAND\n\n")
        self.write("A self-sufficient runtime for containers\n\n")
        self.write("Common Commands:\n")
        self.write("  ps          List containers\n")
        self.write("  images      List images\n")
        self.write("  logs        Fetch the logs of a container\n")
        self.write("  inspect     Return low-level information on Docker objects\n")
        self.write("  exec        Execute a command in a running container\n")
        self.write("  run         Create and run a new container from an image\n")
        self.write("  compose     Docker Compose\n")


commands["/usr/bin/docker"] = Command_docker
commands["docker"] = Command_docker


class Command_docker_compose(Command_docker):
    """docker-compose (v1 binary) — delegates to docker compose handler."""

    def call(self) -> None:
        # Rewrite args as if "docker compose <args>"
        self.args = ["compose"] + list(self.args)
        super().call()


commands["/usr/local/bin/docker-compose"] = Command_docker_compose
commands["/usr/bin/docker-compose"] = Command_docker_compose
commands["docker-compose"] = Command_docker_compose
