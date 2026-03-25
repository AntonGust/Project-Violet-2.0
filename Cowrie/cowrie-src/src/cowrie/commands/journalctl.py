"""
Native journalctl command handler for Cowrie honeypot.

Reads log file content from honeyfs and generates service-specific
journal entries from profile services, producing output consistent
with systemctl and ps.
"""

from __future__ import annotations

import time
from typing import Any

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.fs import FileNotFound

commands = {}

# Map service names to likely log file paths in the profile
_SERVICE_LOG_MAP: dict[str, list[str]] = {
    "sshd": ["/var/log/auth.log", "/var/log/secure"],
    "ssh": ["/var/log/auth.log", "/var/log/secure"],
    "cron": ["/var/log/syslog", "/var/log/auth.log"],
    "borg": ["/var/log/backup.log"],
    "borgbackup": ["/var/log/backup.log"],
    "rsync": ["/var/log/backup.log"],
    "rsyncd": ["/var/log/backup.log"],
    "postfix": ["/var/log/mail.log"],
    "dovecot": ["/var/log/mail.log"],
    "nginx": ["/var/log/nginx/error.log"],
    "apache2": ["/var/log/apache2/error.log"],
    "named": ["/var/log/named/queries.log"],
    "mysql": ["/var/log/mysql/error.log"],
    "mysqld": ["/var/log/mysql/error.log"],
    "docker": ["/var/log/docker_deploy.log"],
    "dockerd": ["/var/log/docker_deploy.log"],
    "jenkins": ["/var/log/jenkins/jenkins.log"],
    "gitea": ["/var/log/gitea/gitea.log"],
    "grafana": ["/var/log/grafana/grafana.log"],
    "prometheus": ["/var/log/grafana/grafana.log"],
    "mosquitto": ["/var/log/mosquitto/mosquitto.log"],
    "openvpn": ["/var/log/openvpn/status.log"],
    "smbd": ["/var/log/samba/log.smbd"],
}

# Template log entries per service type
_SERVICE_TEMPLATES: dict[str, list[str]] = {
    "sshd": [
        "Server listening on 0.0.0.0 port 22.",
        "Server listening on :: port 22.",
        "Received SIGHUP; restarting.",
    ],
    "cron": [
        "pam_unix(cron:session): session opened for user root(uid=0) by (uid=0)",
        "pam_unix(cron:session): session closed for user root",
        "(root) CMD (   cd / && run-parts --report /etc/cron.hourly)",
    ],
    "nginx": [
        "start worker processes",
        "start worker process {pid}",
        "signal process started",
    ],
    "postfix": [
        "starting the Postfix mail system",
        "daemon started -- version 3.4.13, configuration /etc/postfix",
        "connect from unknown[10.0.1.45]",
    ],
    "named": [
        "running as: named -u bind",
        "loaded serial 2024021501",
        "zone internal.corp/IN: loaded serial 2024021501",
    ],
}

_DEFAULT_TEMPLATES = [
    "Started {name}.",
    "{name}[{pid}]: Listening on configured ports.",
    "{name}[{pid}]: Ready to accept connections.",
]


class Command_journalctl(HoneyPotCommand):
    callbacks: list[Any]

    def _get_profile_services(self) -> list[dict[str, Any]]:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("services", [])

    def _find_service(self, name: str) -> dict | None:
        for svc in self._get_profile_services():
            svc_base = svc["name"].split("-")[0]
            if svc_base == name or svc["name"] == name:
                return svc
            if svc_base.rstrip("d") == name.rstrip("d"):
                return svc
        return None

    def call(self) -> None:
        unit = None
        follow = False
        num_lines = 10
        show_help = False
        disk_usage = False
        xe_mode = False

        i = 0
        while i < len(self.args):
            arg = self.args[i]
            if arg == "-u" and i + 1 < len(self.args):
                unit = self.args[i + 1].removesuffix(".service")
                i += 2
                continue
            elif arg.startswith("-u"):
                unit = arg[2:].removesuffix(".service")
            elif arg in ("-f", "--follow"):
                follow = True
            elif arg == "-n" and i + 1 < len(self.args):
                try:
                    num_lines = int(self.args[i + 1])
                except ValueError:
                    pass
                i += 2
                continue
            elif arg.startswith("-n") and arg[2:].isdigit():
                num_lines = int(arg[2:])
            elif arg == "--disk-usage":
                disk_usage = True
            elif arg == "-xe" or (arg.startswith("-") and "x" in arg and "e" in arg):
                xe_mode = True
                num_lines = 20
            elif arg in ("--since", "--until", "--output", "--grep"):
                # Skip these and their argument
                i += 2
                continue
            elif arg in ("-h", "--help"):
                show_help = True
            elif arg == "--no-pager":
                pass  # Silently accept
            i += 1

        if show_help:
            self.write("journalctl [OPTIONS...] [MATCHES...]\n\n")
            self.write("Query the journal.\n\n")
            self.write("Options:\n")
            self.write("  -u --unit=UNIT         Show logs from the specified unit\n")
            self.write("  -f --follow            Follow the journal\n")
            self.write("  -n --lines=INTEGER     Number of journal entries to show\n")
            self.write("  --since=DATE           Show entries since date\n")
            self.write("  --disk-usage           Show total disk usage\n")
            self.write("  -x --catalog           Show explanation texts\n")
            self.write("  -e --pager-end         Jump to end of journal\n")
            return

        if disk_usage:
            self.write("Archived and active journals take up 48.0M in the file system.\n")
            return

        hostname = self.protocol.hostname

        # Header
        boot_time = time.time() - 47 * 86400
        self.write(f"-- Journal begins at {self._fmt_time(boot_time)}, ends at {self._fmt_time(time.time())}. --\n")

        if unit:
            self._show_unit_logs(unit, hostname, num_lines, xe_mode)
        else:
            self._show_generic_logs(hostname, num_lines)

        if follow:
            # Hang like tail -f
            self.callbacks = [self._ignore_input]
            return

    def _show_unit_logs(self, unit: str, hostname: str, num_lines: int, xe_mode: bool) -> None:
        svc = self._find_service(unit)

        # Try honeyfs log files first
        log_lines = self._read_service_logs(unit, num_lines)
        if log_lines:
            for line in log_lines[-num_lines:]:
                self.write(line + "\n")
            return

        # Generate template entries
        pid = svc.get("pid", 1000) if svc else 1000
        svc_name = svc["name"] if svc else unit
        cmd = svc.get("command", svc_name) if svc else unit

        templates = _SERVICE_TEMPLATES.get(unit, _SERVICE_TEMPLATES.get(svc_name.split("-")[0], _DEFAULT_TEMPLATES))

        base_time = time.time() - 47 * 86400
        for i in range(min(num_lines, len(templates) + 3)):
            ts = self._fmt_time(base_time + i * 3600)
            if i == 0:
                msg = f"Started {svc_name}.service - {svc_name}."
            elif i <= len(templates):
                msg = templates[min(i - 1, len(templates) - 1)].format(
                    name=svc_name, pid=pid, port=svc.get("ports", [0])[0] if svc and svc.get("ports") else "")
            else:
                msg = f"{svc_name}[{pid}]: Running normally."
            self.write(f"{ts} {hostname} {svc_name}[{pid}]: {msg}\n")

    def _read_service_logs(self, unit: str, num_lines: int) -> list[str]:
        """Try to read log content from honeyfs for this service."""
        log_paths = _SERVICE_LOG_MAP.get(unit, [])
        # Also try the normalized name
        for alt in [unit + "d", unit.rstrip("d")]:
            log_paths.extend(_SERVICE_LOG_MAP.get(alt, []))

        for log_path in log_paths:
            try:
                resolved = self.fs.resolve_path(log_path, "/")
                contents = self.fs.file_contents(resolved)
                text = contents.decode("utf-8", errors="replace").strip()
                if text:
                    lines = text.split("\n")
                    return lines[-num_lines:]
            except (FileNotFound, FileNotFoundError, Exception):
                continue
        return []

    def _show_generic_logs(self, hostname: str, num_lines: int) -> None:
        """Show generic syslog-style entries from all services."""
        services = self._get_profile_services()
        base_time = time.time() - 300  # Last 5 minutes

        entries = []
        for i, svc in enumerate(services[:num_lines]):
            ts = self._fmt_time(base_time + i * 30)
            pid = svc.get("pid", 1000)
            name = svc["name"]
            entries.append(f"{ts} {hostname} {name}[{pid}]: Running normally.")

        # Pad with system entries if needed
        system_msgs = [
            ("systemd[1]", "Started Daily apt download activities."),
            ("systemd[1]", "Finished Daily Cleanup of Temporary Directories."),
            ("kernel", "audit: type=1400 audit(0): avc:  denied"),
            ("CRON[{pid}]", "pam_unix(cron:session): session opened for user root"),
        ]
        while len(entries) < num_lines:
            idx = len(entries) % len(system_msgs)
            prog, msg = system_msgs[idx]
            ts = self._fmt_time(base_time + len(entries) * 30)
            entries.append(f"{ts} {hostname} {prog}: {msg}")

        for entry in entries[:num_lines]:
            self.write(entry + "\n")

    @staticmethod
    def _fmt_time(epoch: float) -> str:
        return time.strftime("%b %d %H:%M:%S", time.localtime(epoch))

    def _ignore_input(self, line: str) -> None:
        self.callbacks = [self._ignore_input]

    def lineReceived(self, line: str) -> None:
        if hasattr(self, "callbacks") and self.callbacks:
            self.callbacks.pop(0)(line)

    def handle_CTRL_C(self) -> None:
        self.exit()

    def handle_CTRL_D(self) -> None:
        self.exit()


commands["/usr/bin/journalctl"] = Command_journalctl
commands["journalctl"] = Command_journalctl
