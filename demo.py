#!/usr/bin/env python3
# ABOUTME: Demo mode orchestrator for Project Violet.
# ABOUTME: Runs a scripted SSH session against Cowrie to showcase honeypot capabilities.

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import config
os.environ["RUNID"] = config.run_id

import pexpect

from Blue_Lagoon.honeypot_tools import (
    start_dockers, stop_dockers, wait_for_cowrie, wait_for_db, wait_for_all_cowrie,
)
from Blue_Lagoon.credential_chain import build_chain_manifest, inject_next_hop_breadcrumbs
from Blue_Lagoon.compose_generator import generate_honeynet_compose
from Reconfigurator.lure_agent import enrich_lures

PROJECT_ROOT = Path(__file__).resolve().parent

# ANSI formatting
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


@dataclass
class Section:
    """A themed group of demo commands."""
    title: str
    description: str
    commands: list[str] = field(default_factory=list)


def build_demo_commands(profile: dict) -> list[Section]:
    """Build the full demo command sequence from a profile."""
    file_contents = profile.get("file_contents", {})
    services = profile.get("services", [])

    sections: list[Section] = []

    # Section 1: System Reconnaissance (built-in commands)
    sections.append(Section(
        title="System Reconnaissance",
        description="Basic system enumeration — all built-in Cowrie responses",
        commands=["whoami", "uname -a", "hostname", "id", "uptime", "cat /etc/os-release"],
    ))

    # Section 2: Filesystem & Credential Discovery (profile-adaptive)
    cred_patterns = (".env", "wp-config", ".ssh/id_rsa", ".pgpass", ".my.cnf",
                     ".netrc", "credentials", "password", ".npmrc",
                     ".jenkins", ".docker/config")
    fs_commands = ["ls -la /root", "cat /root/.bash_history"]
    for path in sorted(file_contents.keys()):
        if any(pat in path.lower() for pat in cred_patterns):
            fs_commands.append(f"cat {path}")
    # SSH config files
    for path in file_contents:
        if ".ssh/config" in path or path == "/etc/hosts":
            if f"cat {path}" not in fs_commands:
                fs_commands.append(f"cat {path}")
    sections.append(Section(
        title="Filesystem & Credential Discovery",
        description="Profile-seeded files — credentials, SSH keys, environment configs",
        commands=fs_commands,
    ))

    # Section 3: Network & Services (profile-adaptive)
    net_commands = ["ifconfig", "netstat -tlnp", "ps aux"]
    seen_services = set()
    for svc in services:
        name = svc.get("name", "")
        if name and name not in seen_services:
            seen_services.add(name)
            net_commands.append(f"systemctl status {name}")
    sections.append(Section(
        title="Network & Services",
        description="Network configuration and service enumeration (LLM-powered for systemctl)",
        commands=net_commands,
    ))

    # Section 4: LLM-Powered Dynamic Responses
    llm_commands = ["docker ps", "htop", "df -h", "free -m", "crontab -l"]
    # Demo vim on the first file_content path
    if file_contents:
        first_path = next(iter(file_contents))
        llm_commands.append(f"vim {first_path}")
    sections.append(Section(
        title="LLM-Powered Dynamic Responses",
        description="Commands handled entirely by the LLM — cached after first run",
        commands=llm_commands,
    ))

    # Section 5: Lateral Movement Breadcrumbs (profile-adaptive)
    breadcrumb_patterns = ("backup", ".docker", ".kube", ".npmrc", "jenkins", "deploy")
    breadcrumb_commands = []
    for path in sorted(file_contents.keys()):
        if any(pat in path.lower() for pat in breadcrumb_patterns):
            cmd = f"cat {path}"
            # Avoid duplicates with section 2
            if cmd not in fs_commands:
                breadcrumb_commands.append(cmd)
    if breadcrumb_commands:
        sections.append(Section(
            title="Lateral Movement Breadcrumbs",
            description="Credential and config files an attacker would use for pivoting",
            commands=breadcrumb_commands,
        ))

    return sections


class DemoRunner:
    """Orchestrates a scripted demo against a running Cowrie honeypot."""

    # Typing delays (seconds per character)
    SPEED_NORMAL = 0.07
    SPEED_FAST = 0.03

    def __init__(self, profile_path: str, speed: str = "normal"):
        self.profile_path = Path(profile_path)
        self.speed = speed
        self.profile: dict = {}
        self.ssh: pexpect.spawn | None = None
        self.commands_run = 0
        self.cache_hits = 0  # Informational — actual hits tracked by Cowrie

    def setup(self) -> None:
        """Load profile, deploy to Cowrie, start Docker."""
        print(f"\n{BOLD}Loading profile:{RESET} {self.profile_path.name}")
        with open(self.profile_path) as f:
            self.profile = json.load(f)

        self.profile, _lure_chains = enrich_lures(self.profile)

        # Deploy profile to cowrie_config/
        from main import deploy_cowrie_config
        deploy_cowrie_config(self.profile)

        print(f"{BOLD}Starting Docker containers...{RESET}")
        start_dockers()
        wait_for_cowrie()
        wait_for_db()
        print(f"{GREEN}Cowrie is ready.{RESET}\n")

    def connect_ssh(self, retries: int = 10, delay: float = 2.0) -> None:
        """SSH directly to Cowrie on the demo port, retrying until the port is reachable."""
        port = f"22{config.run_id}"

        # Find a valid user credential from the profile
        username, password = self._pick_credentials()

        print(f"{BOLD}Connecting via SSH:{RESET} {username}@localhost:{port}")

        ssh_cmd = (
            f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-p {port} {username}@localhost"
        )

        for attempt in range(1, retries + 1):
            self.ssh = pexpect.spawn(ssh_cmd, encoding="utf-8", timeout=30)
            try:
                self.ssh.expect("[Pp]assword:")
                break  # Port is reachable, got password prompt
            except (pexpect.EOF, pexpect.TIMEOUT):
                self.ssh.close()
                if attempt == retries:
                    raise ConnectionError(
                        f"Could not connect to Cowrie on localhost:{port} "
                        f"after {retries} attempts"
                    )
                print(f"  {DIM}Waiting for SSH port (attempt {attempt}/{retries})...{RESET}")
                time.sleep(delay)

        self.ssh.sendline(password)
        # Wait for shell prompt (anchored to end of line to avoid partial matches)
        self.ssh.expect([r"\$\s*$", r"#\s*$"], timeout=10)
        print(f"{GREEN}Connected!{RESET}\n")

    def _pick_credentials(self) -> tuple[str, str]:
        """Extract a usable username/password from the profile."""
        users = self.profile.get("users", [])
        # Prefer root, fallback to first user with a real hash
        for user in users:
            if user.get("name") == "root" and user.get("password_hash", "*") != "*":
                return "root", "root"
        for user in users:
            if user.get("password_hash", "*") not in ("*", "!"):
                return user["name"], user["name"]
        # Ultimate fallback
        return "root", "root"

    def run_demo(self) -> None:
        """Execute the scripted demo sequence."""
        self._print_profile_info()
        sections = build_demo_commands(self.profile)

        if self.speed == "interactive":
            self._run_interactive(sections)
        else:
            self._run_scripted(sections)

    def _print_profile_info(self) -> None:
        """Print a detailed overview of the loaded profile before running commands."""
        sys_info = self.profile.get("system", {})
        users = self.profile.get("users", [])
        services = self.profile.get("services", [])
        file_contents = self.profile.get("file_contents", {})
        directory_tree = self.profile.get("directory_tree", {})

        print(f"{BOLD}{CYAN}{'='*60}{RESET}")
        print(f"{BOLD}{CYAN}  Profile Overview{RESET}")
        print(f"{BOLD}{CYAN}{'='*60}{RESET}")

        # System info
        print(f"\n  {BOLD}System{RESET}")
        print(f"    OS            : {sys_info.get('os', 'N/A')}")
        print(f"    Hostname      : {sys_info.get('hostname', 'N/A')}")
        print(f"    Kernel        : {sys_info.get('kernel_version', 'N/A')}")
        print(f"    Arch          : {sys_info.get('arch', 'N/A')}")

        # Users
        print(f"\n  {BOLD}Users ({len(users)}){RESET}")
        for u in users:
            name = u.get("name", "?")
            shell = u.get("shell", "?")
            groups = ", ".join(u.get("groups", []))
            login = "login" if "nologin" not in shell else "nologin"
            sudo = " [sudo]" if u.get("sudo_rules") else ""
            print(f"    {name:16s} {login:8s} groups=[{groups}]{sudo}")

        # Services
        print(f"\n  {BOLD}Services ({len(services)}){RESET}")
        for svc in services:
            name = svc.get("name", "?")
            ports = svc.get("ports", [])
            port_str = f" :{', :'.join(str(p) for p in ports)}" if ports else ""
            print(f"    {name:20s}{port_str}")

        # File contents (credential & config files seeded in honeyfs)
        print(f"\n  {BOLD}Seeded Files ({len(file_contents)}){RESET}")
        for path in sorted(file_contents.keys()):
            content = file_contents[path]
            size = len(content.encode())
            print(f"    {path:45s} ({size:,} bytes)")

        # Directory tree paths
        print(f"\n  {BOLD}Directory Tree Paths ({len(directory_tree)}){RESET}")
        for dir_path in sorted(directory_tree.keys()):
            entries = directory_tree[dir_path]
            n_files = sum(1 for e in entries if e.get("type") == "file")
            n_dirs = sum(1 for e in entries if e.get("type") == "dir")
            parts = []
            if n_files:
                parts.append(f"{n_files} files")
            if n_dirs:
                parts.append(f"{n_dirs} dirs")
            print(f"    {dir_path:45s} ({', '.join(parts)})")

        print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
        print(f"{DIM}  Demo will execute commands across {len(build_demo_commands(self.profile))} sections{RESET}")
        print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")
        time.sleep(2.0)

    def _run_scripted(self, sections: list[Section]) -> None:
        """Run all sections automatically with typewriter effect."""
        char_delay = self.SPEED_NORMAL if self.speed == "normal" else self.SPEED_FAST

        for i, section in enumerate(sections, 1):
            self._print_section_header(i, section)
            time.sleep(1.0 if self.speed == "normal" else 0.5)

            for cmd in section.commands:
                self._typewrite_command(cmd, char_delay)
                output = self._read_output()
                self._print_output(output)
                self.commands_run += 1
                # Pause between commands — let viewer read output
                time.sleep(0.8 if self.speed == "fast" else 1.5)

            print()  # Blank line between sections
            time.sleep(0.5 if self.speed == "fast" else 1.0)

    def _run_interactive(self, sections: list[Section]) -> None:
        """Run sections, pausing for Enter between each."""
        for i, section in enumerate(sections, 1):
            self._print_section_header(i, section)
            input(f"  {DIM}Press Enter to run this section...{RESET}")

            for cmd in section.commands:
                self._typewrite_command(cmd, self.SPEED_FAST)
                output = self._read_output()
                self._print_output(output)
                self.commands_run += 1
                time.sleep(0.8)

            print()

    def _print_section_header(self, num: int, section: Section) -> None:
        print(f"{BOLD}{CYAN}{'='*60}{RESET}")
        print(f"{BOLD}{CYAN}  Section {num}: {section.title}{RESET}")
        print(f"{DIM}  {section.description}{RESET}")
        print(f"{BOLD}{CYAN}{'='*60}{RESET}\n")

    def _typewrite_command(self, command: str, delay: float) -> None:
        """Display command with typewriter effect and send to SSH."""
        sys.stdout.write(f"  {GREEN}$ {RESET}")
        for char in command:
            sys.stdout.write(f"{GREEN}{char}{RESET}")
            sys.stdout.flush()
            time.sleep(delay)
        print()

        assert self.ssh is not None
        self.ssh.sendline(command)

    def _read_output(self) -> str:
        """Read SSH output until the next shell prompt."""
        assert self.ssh is not None
        try:
            self.ssh.expect([r"\$\s*$", r"#\s*$"], timeout=15)
            raw = self.ssh.before or ""
            # Strip the echoed command (first line)
            lines = raw.split("\n")
            if len(lines) > 1:
                return "\n".join(lines[1:]).rstrip()
            return raw.rstrip()
        except pexpect.TIMEOUT:
            return "(timeout waiting for response)"
        except pexpect.EOF:
            return "(connection closed)"

    def _print_output(self, output: str) -> None:
        """Print command output with indentation."""
        if not output.strip():
            return
        for line in output.split("\n"):
            print(f"    {line}")

    def print_summary(self) -> None:
        """Print demo statistics."""
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}  Demo Complete{RESET}")
        print(f"{'='*60}")
        print(f"  Commands executed  : {self.commands_run}")
        print(f"  Profile            : {self.profile_path.stem}")
        hostname = self.profile.get("system", {}).get("hostname", "unknown")
        print(f"  Hostname           : {hostname}")
        cache_path = PROJECT_ROOT / "cowrie_config" / "var" / "llm_cache.json"
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    cache = json.load(f)
                print(f"  Cached LLM entries : {len(cache.get('entries', {}))}")
            except (json.JSONDecodeError, OSError):
                pass
        print(f"{'='*60}\n")

    def teardown(self) -> None:
        """Close SSH and stop Docker containers."""
        if self.ssh and self.ssh.isalive():
            try:
                self.ssh.sendline("exit")
                self.ssh.close()
            except Exception:
                pass
        print(f"\n{BOLD}Stopping Docker containers...{RESET}")
        stop_dockers()

    def run(self) -> None:
        """Full demo lifecycle: setup -> connect -> demo -> teardown."""
        try:
            self.setup()
            self.connect_ssh()
            self.run_demo()
            self.print_summary()
        finally:
            self.teardown()


def build_hop_recon_commands(profile: dict, hop_index: int) -> list[Section]:
    """Build recon commands for a single hop in the honeynet chain."""
    file_contents = profile.get("file_contents", {})
    services = profile.get("services", [])
    hostname = profile.get("system", {}).get("hostname", f"hop{hop_index + 1}")

    sections: list[Section] = []

    # System recon
    sections.append(Section(
        title=f"Hop {hop_index + 1} ({hostname}) — Reconnaissance",
        description="System enumeration on this hop",
        commands=["whoami", "hostname", "uname -a", "id", "ifconfig"],
    ))

    # Credential & breadcrumb discovery
    cred_patterns = (
        ".env", "wp-config", ".ssh/id_rsa", ".pgpass", ".my.cnf",
        ".netrc", "credentials", "password", ".npmrc",
        ".jenkins", ".docker/config",
    )
    discovery_commands = ["ls -la /root", "cat /root/.bash_history"]
    for path in sorted(file_contents.keys()):
        if any(pat in path.lower() for pat in cred_patterns):
            discovery_commands.append(f"cat {path}")
    for path in file_contents:
        if ".ssh/config" in path or path == "/etc/hosts":
            cmd = f"cat {path}"
            if cmd not in discovery_commands:
                discovery_commands.append(cmd)

    sections.append(Section(
        title=f"Hop {hop_index + 1} ({hostname}) — Credential Discovery",
        description="Searching for credentials, SSH configs, and lateral movement breadcrumbs",
        commands=discovery_commands,
    ))

    # Network & services (brief)
    net_commands = ["netstat -tlnp", "ps aux"]
    seen = set()
    for svc in services[:3]:  # Limit to first 3 services to keep demo focused
        name = svc.get("name", "")
        if name and name not in seen:
            seen.add(name)
            net_commands.append(f"systemctl status {name}")
    sections.append(Section(
        title=f"Hop {hop_index + 1} ({hostname}) — Services",
        description="Network and service enumeration",
        commands=net_commands,
    ))

    return sections


class HoneyNetDemoRunner(DemoRunner):
    """Orchestrates a multi-hop HoneyNet demo with lateral movement pivots."""

    def __init__(self, chain_profiles: list[str], speed: str = "normal"):
        # Use first profile path for parent constructor
        super().__init__(chain_profiles[0], speed)
        self.chain_profile_paths = [Path(p) for p in chain_profiles]
        self.hop_profiles: list[dict] = []
        self.manifest = None
        self.current_hop: int = 0
        self._honeynet_was_enabled = config.honeynet_enabled

    def setup(self) -> None:
        """Build chain manifest, enrich lures, inject breadcrumbs, deploy, start Docker."""
        # Enable honeynet mode so compose/log paths route correctly
        config.honeynet_enabled = True

        print(f"\n{BOLD}{CYAN}HoneyNet Demo Setup{RESET}")
        print(f"{BOLD}Chain: {' -> '.join(p.stem for p in self.chain_profile_paths)}{RESET}\n")

        # 1. Build chain manifest
        chain_rel = [str(p) for p in self.chain_profile_paths]
        self.manifest = build_chain_manifest(config.run_id, chain_rel)

        # 2. Load, enrich, inject breadcrumbs, deploy per hop
        from main import deploy_cowrie_config

        for i, hop in enumerate(self.manifest.hops):
            profile_path = PROJECT_ROOT / hop.profile_path
            print(f"  {BOLD}Hop {i + 1}:{RESET} {profile_path.name}")

            with open(profile_path) as f:
                profile = json.load(f)

            profile, _lure_chains = enrich_lures(profile)

            # Inject next-hop breadcrumbs (all but last hop)
            if i < len(self.manifest.hops) - 1:
                next_hop = self.manifest.hops[i + 1]
                inject_next_hop_breadcrumbs(profile, hop, next_hop)
                print(f"    Breadcrumbs injected -> {next_hop.hostname} ({next_hop.ip_from_prev})")

            deploy_cowrie_config(profile, hop_index=i)
            self.hop_profiles.append(profile)

        # Use first hop's profile for initial SSH credentials
        self.profile = self.hop_profiles[0]

        # 3. Generate docker-compose.honeynet.yml
        generate_honeynet_compose(self.manifest)

        # 4. Start all containers
        print(f"\n{BOLD}Starting Docker containers ({len(self.manifest.hops)} hops)...{RESET}")
        start_dockers()
        wait_for_all_cowrie(len(self.manifest.hops))
        print(f"{GREEN}All Cowrie instances ready.{RESET}\n")

    def connect_ssh(self, retries: int = 10, delay: float = 2.0) -> None:
        """SSH to Pot1 (entry point)."""
        hop = self.manifest.hops[0]
        port = f"22{config.run_id}"

        username = hop.username
        password = hop.password

        print(f"{BOLD}Connecting to Pot1 (entry):{RESET} {username}@localhost:{port}")

        ssh_cmd = (
            f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
            f"-p {port} {username}@localhost"
        )

        for attempt in range(1, retries + 1):
            self.ssh = pexpect.spawn(ssh_cmd, encoding="utf-8", timeout=30)
            try:
                self.ssh.expect("[Pp]assword:")
                break
            except (pexpect.EOF, pexpect.TIMEOUT):
                self.ssh.close()
                if attempt == retries:
                    raise ConnectionError(
                        f"Could not connect to Cowrie on localhost:{port} "
                        f"after {retries} attempts"
                    )
                print(f"  {DIM}Waiting for SSH port (attempt {attempt}/{retries})...{RESET}")
                time.sleep(delay)

        self.ssh.sendline(password)
        self.ssh.expect([r"\$\s*$", r"#\s*$"], timeout=10)
        self.current_hop = 0
        print(f"{GREEN}Connected to Hop 1!{RESET}\n")

    def _pivot_to_next_hop(self, hop_index: int) -> bool:
        """SSH from current hop to the next hop via Cowrie's SSH proxy.

        Returns True if pivot succeeded.
        """
        next_hop = self.manifest.hops[hop_index]
        ip = next_hop.ip_from_prev
        user = next_hop.username
        password = next_hop.password
        port = next_hop.ssh_port

        print(f"\n{BOLD}{YELLOW}{'='*60}{RESET}")
        print(f"{BOLD}{YELLOW}  PIVOTING: Hop {hop_index} -> Hop {hop_index + 1}{RESET}")
        print(f"{BOLD}{YELLOW}  Target: {user}@{ip}:{port} ({next_hop.hostname}){RESET}")
        print(f"{BOLD}{YELLOW}{'='*60}{RESET}\n")

        char_delay = self.SPEED_NORMAL if self.speed == "normal" else self.SPEED_FAST
        time.sleep(1.0 if self.speed == "normal" else 0.5)

        # Type and send the SSH command
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -p {port} {user}@{ip}"
        self._typewrite_command(ssh_cmd, char_delay)

        # Wait for password prompt from the nested SSH
        assert self.ssh is not None
        try:
            self.ssh.expect("[Pp]assword:", timeout=15)
        except (pexpect.TIMEOUT, pexpect.EOF):
            print(f"    {RED}Failed to get password prompt from {next_hop.hostname}{RESET}")
            return False

        # Send password (display masked)
        sys.stdout.write(f"  {GREEN}Password: {'*' * len(password)}{RESET}\n")
        self.ssh.sendline(password)

        # Cowrie's ssh command has a 2s callLater before starting the proxy,
        # plus paramiko handshake time. We must wait for the proxy to become
        # active BEFORE sending any commands, otherwise lineReceived silently
        # drops input when proxy.active is False and no callbacks remain.
        time.sleep(5)

        # Drain all buffered data (login banner, prompts, etc.) that arrived
        # while the proxy was connecting.
        try:
            while True:
                self.ssh.read_nonblocking(4096, timeout=0.5)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass

        # Now the proxy should be active. Send a sync marker and wait for it
        # to confirm the relay is working end-to-end.
        marker = f"PIVOTSYNC{hop_index}"
        for attempt in range(3):
            self.ssh.sendline(f"echo {marker}")
            try:
                self.ssh.expect(marker, timeout=5)
                # Consume the trailing prompt after the marker
                self.ssh.expect([r"\$", r"#"], timeout=5)
                break
            except (pexpect.TIMEOUT, pexpect.EOF):
                if attempt == 2:
                    print(f"    {RED}Failed to synchronize shell on {next_hop.hostname}{RESET}")
                    return False
                time.sleep(1)

        self.current_hop = hop_index
        print(f"    {GREEN}Pivoted to Hop {hop_index + 1} ({next_hop.hostname})!{RESET}\n")
        time.sleep(1.0)
        return True

    def _exit_hop(self) -> None:
        """Exit the current nested SSH session back to the previous hop."""
        assert self.ssh is not None
        char_delay = self.SPEED_NORMAL if self.speed == "normal" else self.SPEED_FAST
        self._typewrite_command("exit", char_delay)
        try:
            self.ssh.expect([r"\$", r"#"], timeout=10)
        except (pexpect.TIMEOUT, pexpect.EOF):
            pass
        self.current_hop -= 1

    def run_demo(self) -> None:
        """Execute the multi-hop demo: recon each hop, pivot, repeat."""
        self._print_honeynet_overview()

        num_hops = len(self.manifest.hops)

        for hop_idx in range(num_hops):
            profile = self.hop_profiles[hop_idx]
            sections = build_hop_recon_commands(profile, hop_idx)

            if self.speed == "interactive":
                self._run_interactive(sections)
            else:
                self._run_scripted(sections)

            # Pivot to next hop (if not the last one)
            if hop_idx < num_hops - 1:
                success = self._pivot_to_next_hop(hop_idx + 1)
                if not success:
                    print(f"{YELLOW}Pivot failed — ending demo at Hop {hop_idx + 1}{RESET}")
                    break

        # Exit nested sessions back to pot1
        while self.current_hop > 0:
            self._exit_hop()

    def _print_honeynet_overview(self) -> None:
        """Print an overview of the entire honeynet chain before running commands."""
        num_hops = len(self.manifest.hops)

        print(f"{BOLD}{CYAN}{'='*60}{RESET}")
        print(f"{BOLD}{CYAN}  HoneyNet Demo — {num_hops}-Hop Chain{RESET}")
        print(f"{BOLD}{CYAN}{'='*60}{RESET}")

        for i, hop in enumerate(self.manifest.hops):
            profile = self.hop_profiles[i]
            hostname = profile.get("system", {}).get("hostname", "?")
            n_files = len(profile.get("file_contents", {}))
            n_services = len(profile.get("services", []))
            arrow = "  [ENTRY]" if i == 0 else ""

            print(f"\n  {BOLD}Hop {i + 1}: {hostname}{arrow}{RESET}")
            print(f"    IP           : {hop.ip_from_prev}")
            print(f"    Credentials  : {hop.username} / {hop.password}")
            print(f"    Profile      : {Path(hop.profile_path).stem}")
            print(f"    Seeded files : {n_files}")
            print(f"    Services     : {n_services}")

        # Show network topology
        print(f"\n  {BOLD}Network Topology{RESET}")
        topo_parts = [f"Attacker -> {self.manifest.hops[0].hostname}"]
        for i in range(1, num_hops):
            topo_parts.append(self.manifest.hops[i].hostname)
        print(f"    {' -> '.join(topo_parts)}")

        print(f"\n{BOLD}{CYAN}{'='*60}{RESET}\n")
        time.sleep(2.0)

    def print_summary(self) -> None:
        """Print demo stats and session correlation report."""
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}  HoneyNet Demo Complete{RESET}")
        print(f"{'='*60}")
        print(f"  Commands executed  : {self.commands_run}")
        print(f"  Hops in chain      : {len(self.manifest.hops)}")
        print(f"  Profiles           : {', '.join(Path(h.profile_path).stem for h in self.manifest.hops)}")

        # Per-hop LLM cache stats
        for i in range(len(self.manifest.hops)):
            cache_path = PROJECT_ROOT / f"cowrie_config_hop{i + 1}" / "var" / "llm_cache.json"
            if cache_path.exists():
                try:
                    with open(cache_path) as f:
                        cache = json.load(f)
                    print(f"  Hop {i + 1} cached LLM  : {len(cache.get('entries', {}))}")
                except (json.JSONDecodeError, OSError):
                    pass

        print(f"{'='*60}\n")

        # Session correlation report
        from Purple.session_correlator import correlate_sessions, print_correlation_report
        try:
            journeys = correlate_sessions(self.manifest)
            print_correlation_report(journeys)
        except Exception as e:
            print(f"{DIM}  (Session correlation skipped: {e}){RESET}")

    def teardown(self) -> None:
        """Close SSH, stop Docker, restore honeynet_enabled."""
        if self.ssh and self.ssh.isalive():
            try:
                # Exit any nested sessions
                for _ in range(self.current_hop + 1):
                    self.ssh.sendline("exit")
                    time.sleep(0.3)
                self.ssh.close()
            except Exception:
                pass
        print(f"\n{BOLD}Stopping Docker containers...{RESET}")
        stop_dockers()
        # Restore original config state
        config.honeynet_enabled = self._honeynet_was_enabled

    def run(self) -> None:
        """Full honeynet demo lifecycle."""
        try:
            self.setup()
            self.connect_ssh()
            self.run_demo()
            self.print_summary()
        finally:
            self.teardown()
