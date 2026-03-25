# Copyright (c) 2009 Upi Tamminen <desaster@gmail.com>
# See the COPYRIGHT file for more information


from __future__ import annotations

import getopt
import hashlib
import os
import re
import socket
from twisted.internet import reactor
from twisted.python import log

from cowrie.core.config import CowrieConfig
from cowrie.shell.command import HoneyPotCommand
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

commands = {}


OUTPUT = [
    "usage: ssh [-46AaCfGgKkMNnqsTtVvXxYy] [-B bind_interface]",
    "           [-b bind_address] [-c cipher_spec] [-D [bind_address:]port]",
    "           [-E log_file] [-e escape_char] [-F configfile] [-I pkcs11]",
    "           [-i identity_file] [-J [user@]host[:port]] [-L address]",
    "           [-l login_name] [-m mac_spec] [-O ctl_cmd] [-o option] [-p port]",
    "           [-Q query_option] [-R address] [-S ctl_path] [-W host:port]",
    "           [-w local_tun[:remote_tun]] destination [command]",
]


class Command_ssh(HoneyPotCommand):
    """
    ssh
    """

    host: str
    port: int
    callbacks: list[Callable]

    def valid_ip(self, address: str) -> bool:
        try:
            socket.inet_aton(address)
        except Exception:
            return False
        else:
            return True

    def _get_known_hosts(self) -> set[str]:
        """Parse /etc/hosts from the VFS to get known hostnames and IPs."""
        known: set[str] = set()
        try:
            hosts_bytes = self.fs.file_contents("/etc/hosts")
            for line in hosts_bytes.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts:
                    known.add(parts[0])       # IP address
                    known.update(parts[1:])    # hostnames
        except Exception:
            pass
        return known

    def _resolve_host_ip(self, host: str) -> str | None:
        """Resolve a hostname to an IP using VFS /etc/hosts. Returns None if not found."""
        try:
            hosts_bytes = self.fs.file_contents("/etc/hosts")
            for line in hosts_bytes.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    ip = parts[0]
                    hostnames = parts[1:]
                    if host in hostnames:
                        return ip
        except Exception:
            pass
        return None

    def start(self) -> None:
        try:
            options = "-1246AaCfgKkMNnqsTtVvXxYb:c:D:e:F:i:L:l:m:O:o:p:R:S:w:"
            optlist, args = getopt.getopt(self.args, options)
        except getopt.GetoptError:
            self.write("Unrecognized option\n")
            self.exit()
            return

        self.port = 22  # default SSH port

        for opt in optlist:
            if opt[0] == "-V":
                self.write(
                    CowrieConfig.get(
                        "shell",
                        "ssh_version",
                        fallback="OpenSSH_7.9p1, OpenSSL 1.1.1a  20 Nov 2018",
                    )
                    + "\n"
                )
                self.exit()
                return
            if opt[0] == "-p":
                try:
                    self.port = int(opt[1])
                except ValueError:
                    self.write(f"ssh: bad port '{opt[1]}'\n")
                    self.exit()
                    return

        if not len(args):
            for line in OUTPUT:
                self.write(f"{line}\n")
            self.exit()
            return

        user, host = "root", args[0]
        for opt in optlist:
            if opt[0] == "-l":
                user = opt[1]
        if args[0].count("@"):
            user, host = args[0].split("@", 1)

        if re.match("^[0-9.]+$", host):
            if self.valid_ip(host):
                self.ip = host
            else:
                self.write(
                    f"ssh: Could not resolve hostname {host}: "
                    "Name or service not known\n"
                )
                self.exit()
                return
        else:
            s = hashlib.md5(host.encode()).hexdigest()
            self.ip = ".".join(
                [str(int(x, 16)) for x in (s[0:2], s[2:4], s[4:6], s[6:8])]
            )

        self.host = host
        self.user = user

        # In honeynet mode, check if host is reachable before prompting
        if os.environ.get("HONEYNET_MODE") == "true":
            known_hosts = self._get_known_hosts()
            # Resolve hostname to IP if needed
            target = host
            if not re.match(r"^[0-9.]+$", host):
                resolved = self._resolve_host_ip(host)
                if resolved:
                    target = resolved

            if target not in known_hosts and host not in known_hosts:
                # Unknown host — fast fail, no password prompt
                self.write(
                    f"ssh: connect to host {self.host} port {self.port}: Connection refused\n"
                )
                self.exit()
                return

        # Known host or non-honeynet mode — show password prompt
        self.write(
            f"Warning: Permanently added '{self.host}' (RSA) to the list of known hosts.\n"
        )
        self.write(f"{self.user}@{self.host}'s password: ")
        self.protocol.password_input = True
        self.callbacks = [self.wait]

    def wait(self, line: str) -> None:
        self._pending_proxy = True
        reactor.callLater(2, self.finish, line)  # type: ignore[attr-defined]

    def finish(self, password: str) -> None:
        self.protocol.password_input = False
        self._last_password = password

        if os.environ.get("HONEYNET_MODE") == "true":
            try:
                from cowrie.commands.ssh_proxy import SSHProxySession

                # Save state so we can restore on disconnect
                self._saved_hostname = self.protocol.hostname
                self._saved_cwd = self.protocol.cwd

                # Use the parsed port (default 22 → map to 2222 for Docker)
                proxy_port = 2222 if self.port == 22 else self.port

                self.proxy = SSHProxySession(
                    self.host, proxy_port, self.user, password, self
                )
                from twisted.internet import threads
                d = threads.deferToThread(self.proxy.connect)
                d.addCallback(self._proxy_connect_result)
                d.addErrback(self._proxy_connect_error)
                return
            except Exception as e:
                log.msg(f"SSH proxy import/init failed: {e}")

        self._simulated_login(password)

    def _proxy_connect_result(self, result: str) -> None:
        """Handle proxy connection result."""
        from cowrie.commands.ssh_proxy import SSHProxySession

        if result == SSHProxySession.CONNECT_AUTH_FAILED:
            # Auth failed — "Permission denied" already written by proxy
            self.exit()
        elif result == SSHProxySession.CONNECT_UNREACHABLE:
            # Host unreachable — report timeout (no fake shell loopback)
            self.write(f"ssh: connect to host {self.host} port {self.port}: Connection timed out\n")
            self.exit()

    def _proxy_connect_error(self, failure) -> None:
        """Handle proxy connection error — report timeout."""
        log.msg(f"SSH proxy connection error: {failure}")
        self.write(f"ssh: connect to host {self.host} port {self.port}: Connection timed out\n")
        self.exit()

    def lineReceived(self, line: str) -> None:
        log.msg("INPUT (ssh):", line)
        if hasattr(self, 'proxy') and self.proxy.active:
            self.proxy.relay_input(line)
        elif len(self.callbacks):
            self.callbacks.pop(0)(line)

    def handle_CTRL_C(self) -> None:
        if hasattr(self, 'proxy') and self.proxy.active:
            self.proxy.relay_input_bytes(b'\x03')
        else:
            self.write("^C\n")
            self.exit()

    def handle_CTRL_D(self) -> None:
        if hasattr(self, 'proxy') and self.proxy.active:
            self.proxy.disconnect()
        else:
            self.exit()


commands["/usr/bin/ssh"] = Command_ssh
commands["ssh"] = Command_ssh
