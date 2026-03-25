"""
Native ss (socket statistics) command handler for Cowrie honeypot.

Reads services from the deployed profile to produce output consistent
with netstat, ps, and systemctl.
"""

from __future__ import annotations

from typing import Any

from cowrie.shell.command import HoneyPotCommand

commands = {}

# Well-known port-to-service name mapping (reused from netstat)
_PORT_NAMES: dict[int, str] = {
    22: "ssh", 25: "smtp", 53: "domain", 80: "http",
    110: "pop3", 143: "imap", 443: "https", 873: "rsync",
    993: "imaps", 995: "pop3s", 3306: "mysql", 5432: "postgresql",
    6379: "redis", 8080: "http-alt", 8443: "https-alt", 9090: "prometheus",
    9100: "node-exp", 27017: "mongod",
}


class Command_ss(HoneyPotCommand):
    def _get_profile_services(self) -> list[dict[str, Any]]:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("services", [])

    def call(self) -> None:
        show_tcp = False
        show_udp = False
        show_listen = False
        show_numeric = False
        show_processes = False
        show_all = False
        show_help = False

        for arg in self.args:
            if arg.startswith("-") and not arg.startswith("--"):
                for ch in arg[1:]:
                    if ch == "t":
                        show_tcp = True
                    elif ch == "u":
                        show_udp = True
                    elif ch == "l":
                        show_listen = True
                    elif ch == "n":
                        show_numeric = True
                    elif ch == "p":
                        show_processes = True
                    elif ch == "a":
                        show_all = True
                    elif ch == "h":
                        show_help = True
                    elif ch == "4":
                        pass  # IPv4 only, default anyway
                    elif ch == "6":
                        pass  # IPv6, we skip
            elif arg in ("--help", "-h"):
                show_help = True

        if show_help:
            self.write("Usage: ss [ OPTIONS ]\n")
            self.write("   ss [ OPTIONS ] [ FILTER ]\n")
            self.write("   -h, --help          this message\n")
            self.write("   -t, --tcp           display only TCP sockets\n")
            self.write("   -u, --udp           display only UDP sockets\n")
            self.write("   -l, --listening     display listening sockets\n")
            self.write("   -a, --all           display all sockets\n")
            self.write("   -n, --numeric       don't resolve service names\n")
            self.write("   -p, --processes     show process using socket\n")
            return

        # Default: if no protocol specified, show tcp
        if not show_tcp and not show_udp:
            show_tcp = True

        # Default: if neither -l nor -a, show established only
        if not show_listen and not show_all:
            # Show current SSH connection
            self._show_header(show_processes)
            self._show_established(show_numeric, show_processes)
            return

        self._show_header(show_processes)

        services = self._get_profile_services()

        if show_listen or show_all:
            if show_tcp:
                self._show_listening_tcp(services, show_numeric, show_processes)
            if show_udp:
                # No UDP services typically, but show placeholder
                pass

        if show_all:
            self._show_established(show_numeric, show_processes)

    def _show_header(self, show_processes: bool) -> None:
        hdr = "Netid  State      Recv-Q  Send-Q    Local Address:Port      Peer Address:Port  "
        if show_processes:
            hdr += "Process"
        self.write(hdr + "\n")

    def _show_listening_tcp(self, services: list, show_numeric: bool, show_processes: bool) -> None:
        if not services:
            # Fallback: just SSH
            self._write_listen_line(22, None, None, show_numeric, show_processes)
            return

        for svc in services:
            for port in svc.get("ports", []):
                cmd = svc.get("command", "")
                prog = cmd.split("/")[-1].split()[0] if cmd else svc.get("name", "")
                pid = svc.get("pid")
                self._write_listen_line(port, pid, prog, show_numeric, show_processes)

    def _write_listen_line(self, port: int, pid: int | None, prog: str | None,
                           show_numeric: bool, show_processes: bool) -> None:
        port_str = str(port) if show_numeric else _PORT_NAMES.get(port, str(port))
        local = f"0.0.0.0:{port_str}"
        peer = "0.0.0.0:*"
        line = f"tcp    LISTEN     0       128       {local:<22} {peer:<20}"
        if show_processes and pid and prog:
            line += f" users:((\"{prog}\",pid={pid},fd=3))"
        self.write(line + "\n")

    def _show_established(self, show_numeric: bool, show_processes: bool) -> None:
        s_name = self.protocol.kippoIP
        c_name = self.protocol.clientIP
        s_port = "22" if show_numeric else "ssh"
        c_port = str(self.protocol.realClientPort)
        local = f"{s_name}:{s_port}"
        peer = f"{c_name}:{c_port}"
        line = f"tcp    ESTAB      0       0         {local:<22} {peer:<20}"
        if show_processes:
            line += " users:((\"sshd\",pid=$$,fd=3))"
        self.write(line + "\n")


commands["/usr/bin/ss"] = Command_ss
commands["ss"] = Command_ss
