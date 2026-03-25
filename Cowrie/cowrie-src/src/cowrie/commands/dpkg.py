"""
dpkg command implementation for Cowrie honeypot.

Reads installed_packages from the profile and returns realistic output
for dpkg -l, dpkg -s, dpkg --list, dpkg --status, dpkg -L.
"""

from __future__ import annotations

from typing import Any

from cowrie.shell.command import HoneyPotCommand

commands = {}


class Command_dpkg(HoneyPotCommand):
    """dpkg command — package query operations from profile data."""

    def _get_packages(self) -> list[dict[str, Any]]:
        """Load installed_packages from the profile."""
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("installed_packages", [])

    def start(self) -> None:
        if not self.args:
            self._show_help()
            return

        arg = self.args[0]

        if arg in ("-l", "--list"):
            self._do_list()
        elif arg in ("-s", "--status"):
            self._do_status()
        elif arg in ("-L", "--listfiles"):
            self._do_listfiles()
        elif arg in ("--version",):
            self._do_version()
        elif arg in ("-h", "--help"):
            self._show_help()
        else:
            self.errorWrite(f"dpkg: error: unknown option {arg}\n")
            self.errorWrite("Type dpkg --help for help.\n")

        self.exit()

    def _do_version(self) -> None:
        self.write("Debian 'dpkg' package management program version 1.20.12 (amd64).\n")

    def _do_list(self) -> None:
        """dpkg -l [pattern] — list packages."""
        packages = self._get_packages()
        if not packages:
            self.write("No packages found.\n")
            return

        # If a specific package pattern is given, filter
        pattern = self.args[1] if len(self.args) > 1 else None

        # Header
        self.write(
            "Desired=Unknown/Install/Remove/Purge/Hold\n"
            "| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend\n"
            "|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)\n"
            "||/ Name                           Version                      Architecture Description\n"
            "+++-==============================-============================-============-===============================\n"
        )

        for pkg in packages:
            name = pkg.get("name", "unknown")
            version = pkg.get("version", "0.0.0")

            if pattern and pattern not in name:
                continue

            desc = name  # Simple fallback description
            self.write(
                f"ii  {name:<30s} {version:<28s} {'amd64':<12s} {desc}\n"
            )

    def _do_status(self) -> None:
        """dpkg -s <package> — show package status."""
        if len(self.args) < 2:
            self.errorWrite("dpkg-query: error: --status needs a valid package name\n")
            return

        target = self.args[1]
        packages = self._get_packages()

        for pkg in packages:
            if pkg["name"] == target:
                version = pkg.get("version", "0.0.0")
                self.write(
                    f"Package: {target}\n"
                    f"Status: install ok installed\n"
                    f"Priority: optional\n"
                    f"Section: misc\n"
                    f"Installed-Size: {len(target) * 127}\n"
                    f"Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>\n"
                    f"Architecture: amd64\n"
                    f"Version: {version}\n"
                    f"Description: {target}\n"
                )
                return

        self.errorWrite(
            f"dpkg-query: package '{target}' is not installed and no information is available\n"
        )

    def _do_listfiles(self) -> None:
        """dpkg -L <package> — list files owned by package."""
        if len(self.args) < 2:
            self.errorWrite("dpkg-query: error: --listfiles needs a valid package name\n")
            return

        target = self.args[1]
        packages = self._get_packages()
        found = any(pkg["name"] == target for pkg in packages)

        if not found:
            self.errorWrite(f"dpkg-query: package '{target}' is not installed\n")
            return

        # Return plausible file list
        self.write(
            f"/.\n"
            f"/usr\n"
            f"/usr/bin\n"
            f"/usr/bin/{target}\n"
            f"/usr/share\n"
            f"/usr/share/doc\n"
            f"/usr/share/doc/{target}\n"
            f"/usr/share/doc/{target}/copyright\n"
            f"/usr/share/doc/{target}/changelog.Debian.gz\n"
        )

    def _show_help(self) -> None:
        self.write(
            "Usage: dpkg [<option> ...] <command>\n"
            "\n"
            "Commands:\n"
            "  -l|--list [<pattern> ...]   List packages matching given pattern.\n"
            "  -s|--status <package> ...   Display package status details.\n"
            "  -L|--listfiles <package> .. List files 'owned' by package(s).\n"
            "  -S|--search <pattern> ...   Find package(s) owning file(s).\n"
            "  --version                   Show the version.\n"
            "  --help                      Show this help message.\n"
        )
        self.exit()


commands["/usr/bin/dpkg"] = Command_dpkg
commands["dpkg"] = Command_dpkg
commands["/usr/bin/dpkg-query"] = Command_dpkg
commands["dpkg-query"] = Command_dpkg
