"""
Native systemctl command handler for Cowrie honeypot.

Reads services from the deployed profile to produce output consistent
with ps, ss, and netstat.
"""

from __future__ import annotations

import time
from typing import Any

from cowrie.shell.command import HoneyPotCommand

commands = {}


class Command_systemctl(HoneyPotCommand):
    def _get_profile_services(self) -> list[dict[str, Any]]:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("services", [])

    def _find_service(self, name: str) -> dict | None:
        """Find a service by name (loose match: 'ssh' matches 'sshd')."""
        services = self._get_profile_services()
        # Exact match first
        for svc in services:
            svc_name = svc["name"].split("-")[0]
            if svc_name == name or svc["name"] == name:
                return svc
        # Loose match: strip trailing 'd' or add 'd'
        for svc in services:
            svc_name = svc["name"].split("-")[0]
            if svc_name.rstrip("d") == name.rstrip("d"):
                return svc
        # Substring match
        for svc in services:
            if name in svc["name"] or svc["name"] in name:
                return svc
        return None

    def call(self) -> None:
        if not self.args:
            self.write("systemctl: missing command\n")
            self.write("Try 'systemctl --help' for more information.\n")
            return

        subcmd = self.args[0]

        if subcmd in ("--version",):
            self.write("systemd 245 (245.4-4ubuntu3.22)\n")
            self.write("+PAM +AUDIT +SELINUX +IMA +APPARMOR +SMACK +SYSVINIT +UTMP\n")
            return

        if subcmd in ("--help", "-h"):
            self.write("systemctl [OPTIONS...] COMMAND ...\n\n")
            self.write("Query or send control commands to the system manager.\n\n")
            self.write("Unit Commands:\n")
            self.write("  list-units [PATTERN...]   List units currently in memory\n")
            self.write("  status [PATTERN...|PID...] Show runtime status of units\n")
            self.write("  start UNIT...              Start units\n")
            self.write("  stop UNIT...               Stop units\n")
            self.write("  restart UNIT...            Restart units\n")
            self.write("  enable UNIT...             Enable units\n")
            self.write("  disable UNIT...            Disable units\n")
            return

        if subcmd == "status":
            self._do_status()
        elif subcmd in ("list-units", "list-unit-files"):
            self._do_list_units()
        elif subcmd in ("start", "stop", "restart", "reload", "enable", "disable"):
            self._do_control(subcmd)
        elif subcmd == "is-active":
            self._do_is_active()
        elif subcmd == "is-enabled":
            self._do_is_enabled()
        elif subcmd == "daemon-reload":
            pass  # Silent success
        else:
            self.write(f"Unknown command verb {subcmd}.\n")

    def _normalize_unit(self, name: str) -> str:
        """Strip .service suffix for matching."""
        return name.removesuffix(".service")

    def _do_status(self) -> None:
        if len(self.args) < 2:
            # No unit specified — show system status
            self.write(f"● {self.protocol.hostname}\n")
            self.write(f"    State: running\n")
            self.write(f"     Jobs: 0 queued\n")
            self.write(f"   Failed: 0 units\n")
            return

        unit_name = self._normalize_unit(self.args[1])
        svc = self._find_service(unit_name)

        if svc:
            pid = svc.get("pid", 1)
            cmd = svc.get("command", svc["name"])
            svc_name = svc["name"]
            # Compute uptime string
            boot_str = time.strftime("%a %Y-%m-%d %H:%M:%S UTC", time.gmtime(time.time() - 47 * 86400))
            self.write(f"● {svc_name}.service - {svc_name}\n")
            self.write(f"     Loaded: loaded (/lib/systemd/system/{svc_name}.service; enabled)\n")
            self.write(f"     Active: active (running) since {boot_str}; 47 days ago\n")
            self.write(f"   Main PID: {pid} ({cmd.split('/')[-1].split()[0]})\n")
            self.write(f"      Tasks: 1 (limit: 4915)\n")
            self.write(f"     Memory: 5.4M\n")
            self.write(f"        CPU: 1.234s\n")
            self.write(f"     CGroup: /system.slice/{svc_name}.service\n")
            self.write(f"             └─{pid} {cmd}\n")
        else:
            unit = unit_name
            self.write(f"● {unit}.service - {unit}\n")
            self.write(f"     Loaded: loaded (/lib/systemd/system/{unit}.service; disabled)\n")
            self.write(f"     Active: inactive (dead)\n")

    def _do_list_units(self) -> None:
        services = self._get_profile_services()
        self.write("UNIT                          LOAD      ACTIVE   SUB     DESCRIPTION\n")
        for svc in services:
            name = svc["name"]
            unit = f"{name}.service"
            self.write(f"  {unit:<28}loaded    active   running {name}\n")
        # Always show some system units
        for sys_unit in ["systemd-journald.service", "systemd-logind.service", "systemd-udevd.service"]:
            self.write(f"  {sys_unit:<28}loaded    active   running {sys_unit.split('.')[0]}\n")
        total = len(services) + 3
        self.write(f"\n{total} loaded units listed.\n")

    def _do_control(self, action: str) -> None:
        if len(self.args) < 2:
            self.write(f"Too few arguments.\n")
            return
        # Silently accept — honeypot shouldn't resist
        if action in ("enable", "disable"):
            unit = self.args[1]
            if action == "enable":
                self.write(f"Created symlink /etc/systemd/system/multi-user.target.wants/{unit} → /lib/systemd/system/{unit}.\n")

    def _do_is_active(self) -> None:
        if len(self.args) < 2:
            self.write("unknown\n")
            return
        unit_name = self._normalize_unit(self.args[1])
        svc = self._find_service(unit_name)
        self.write("active\n" if svc else "inactive\n")

    def _do_is_enabled(self) -> None:
        if len(self.args) < 2:
            self.write("unknown\n")
            return
        unit_name = self._normalize_unit(self.args[1])
        svc = self._find_service(unit_name)
        self.write("enabled\n" if svc else "disabled\n")


commands["/usr/bin/systemctl"] = Command_systemctl
commands["systemctl"] = Command_systemctl
