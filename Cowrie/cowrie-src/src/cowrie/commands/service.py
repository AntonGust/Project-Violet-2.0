# Copyright (c) 2015 Michel Oosterhof <michel@oosterhof.net>
# All rights reserved.

"""
This module contains the service commnad
"""

from __future__ import annotations

import getopt

from cowrie.shell.command import HoneyPotCommand

commands = {}


class Command_service(HoneyPotCommand):
    """
    By Giannis Papaioannou <giannispapcod7@gmail.com>
    """

    def _get_profile_services(self) -> list:
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("services", [])

    def status_all(self) -> None:
        # Base system services (always present on a server)
        base_running = {"cron", "dbus", "networking", "procps", "rsyslog", "udev"}
        base_stopped = {
            "bootmisc.sh", "checkfs.sh", "checkroot.sh", "hostname.sh",
            "hwclock.sh", "killprocs", "mountall.sh", "mountnfs.sh",
            "rc.local", "sendsigs", "umountfs", "umountroot",
        }

        # Add profile services as running
        profile_services = self._get_profile_services()
        for svc in profile_services:
            svc_name = svc["name"].split("-")[0]
            base_running.add(svc_name)
            base_stopped.discard(svc_name)

        # Also add ssh if sshd is in profile
        if any(s["name"].startswith("ssh") for s in profile_services):
            base_running.add("ssh")

        lines = []
        for svc in sorted(base_running):
            lines.append(f" [ + ]  {svc}")
        for svc in sorted(base_stopped):
            lines.append(f" [ - ]  {svc}")
        for line in lines:
            self.write(line + "\n")

    def help(self) -> None:
        output = "Usage: service < option > | --status-all | [ service_name [ command | --full-restart ] ]"
        self.write(output + "\n")

    def call(self) -> None:
        try:
            opts, args = getopt.gnu_getopt(
                self.args, "h", ["help", "status-all", "full-restart"]
            )
        except getopt.GetoptError:
            self.help()
            return

        if not opts and not args:
            self.help()
            return

        for o, _a in opts:
            if o in ("--help") or o in ("-h"):
                self.help()
                return
            elif o in ("--status-all"):
                self.status_all()
        """
        Ubuntu shows no response when stopping, starting
        leviathan@ubuntu:~$ sudo service ufw stop
        leviathan@ubuntu:~$ sudo service ufw start
        leviathan@ubuntu:~$
        """


commands["/usr/sbin/service"] = Command_service
commands["service"] = Command_service
