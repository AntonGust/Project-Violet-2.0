# ABOUTME: nmap command handler for Cowrie honeypot.
# ABOUTME: Delegates to LLM fallback with network context for realistic scan output.
# ABOUTME: Falls back to minimal static output when LLM is unavailable.

from __future__ import annotations

from twisted.python import log

from cowrie.core.config import CowrieConfig
from cowrie.shell.command import HoneyPotCommand

commands = {}

hybrid_llm_enabled = CowrieConfig.getboolean("hybrid_llm", "enabled", fallback=False)

NMAP_VERSION = "7.94"


class Command_nmap(HoneyPotCommand):
    """
    nmap command — delegates to LLM fallback for realistic output.
    """

    def start(self) -> None:
        # Check for --help / --version first
        for arg in self.args:
            if arg in ("--help", "-h"):
                self._show_help()
                return
            if arg in ("--version", "-V"):
                self.write(f"Nmap version {NMAP_VERSION} ( https://nmap.org )\n")
                self.exit()
                return

        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if hybrid_llm_enabled and handler:
            cmd_string = "nmap " + " ".join(self.args)
            d = handler.handle_command(cmd_string)
            d.addCallback(self._write_and_exit)
            d.addErrback(self._error_and_exit)
        else:
            # Minimal static output for when LLM is unavailable
            self._write_static_output()

    def _write_and_exit(self, response: str) -> None:
        if response:
            if not response.endswith("\n"):
                response += "\n"
            self.write(response)
        else:
            self._write_static_output()
        self.exit()

    def _error_and_exit(self, failure) -> None:
        log.msg(f"nmap LLM fallback error: {failure}")
        self._write_static_output()
        self.exit()

    def _write_static_output(self) -> None:
        """Minimal static output — ping scan with no hosts up."""
        self.write(f"Starting Nmap {NMAP_VERSION} ( https://nmap.org )\n")
        self.write(f"Nmap done: 0 IP addresses (0 hosts up) scanned in 3.02 seconds\n")

    def _show_help(self) -> None:
        self.write(f"""Nmap {NMAP_VERSION} ( https://nmap.org )
Usage: nmap [Scan Type(s)] [Options] {{target specification}}
TARGET SPECIFICATION:
  -iL <inputfilename>: Input from list of hosts/networks
  -iR <num hosts>: Choose random targets
  --exclude <host1[,host2][,host3],...>: Exclude hosts/networks
HOST DISCOVERY:
  -sL: List Scan - simply list targets to scan
  -sn: Ping Scan - disable port scan
  -Pn: Treat all hosts as online -- skip host discovery
  -PS/PA/PU/PY[portlist]: TCP SYN/ACK, UDP or SCTP discovery to given ports
SCAN TECHNIQUES:
  -sS/sT/sA/sW/sM: TCP SYN/Connect()/ACK/Window/Maimon scans
  -sU: UDP Scan
  -sN/sF/sX: TCP Null, FIN, and Xmas scans
SERVICE/VERSION DETECTION:
  -sV: Probe open ports to determine service/version info
  -sC: equivalent to --script=default
OS DETECTION:
  -O: Enable OS detection
OUTPUT:
  -oN/-oX/-oS/-oG <file>: Output scan in normal, XML, s|<rIpt kIddi3, and Grepable format
MISC:
  -v: Increase verbosity level (use -vv or more for greater effect)
  -A: Enable OS detection, version detection, script scanning, and traceroute
EXAMPLES:
  nmap -v -A scanme.nmap.org
  nmap -v -sn 192.168.0.0/16 10.0.0.0/8
  nmap -v -iR 10000 -Pn -p 80
""")
        self.exit()


commands["nmap"] = Command_nmap
commands["/usr/bin/nmap"] = Command_nmap
commands["/usr/local/bin/nmap"] = Command_nmap
