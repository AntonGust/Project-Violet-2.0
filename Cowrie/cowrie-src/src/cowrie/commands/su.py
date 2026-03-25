# ABOUTME: Implementation of the 'su' command for Cowrie honeypot.
# ABOUTME: Handles user switching with password prompts when run as non-root,
# ABOUTME: and silent success when run as root.

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from twisted.python import log

from cowrie.shell.command import HoneyPotCommand

if TYPE_CHECKING:
    from collections.abc import Callable

commands = {}


class Command_su(HoneyPotCommand):
    """
    su command implementation.
    - As root: switch to target user silently (no password needed).
    - As non-root: prompt for password, then succeed or fail.
    """

    callbacks: list[Callable]

    def _get_profile_users(self) -> list[dict[str, Any]]:
        """Get user list from profile."""
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("users", [])

    def _user_exists(self, username: str) -> bool:
        """Check if a user exists in the profile."""
        users = self._get_profile_users()
        if users:
            return any(u["name"] == username for u in users)
        # Fallback: assume root and common users exist
        return username in ("root", "deploy", "www-data", "mysql", "nobody")

    def _get_user_shell(self, username: str) -> str:
        """Get the user's shell from profile."""
        for u in self._get_profile_users():
            if u["name"] == username:
                return u.get("shell", "/bin/bash")
        return "/bin/bash"

    def _get_user_home(self, username: str) -> str:
        """Get the user's home directory from profile."""
        for u in self._get_profile_users():
            if u["name"] == username:
                return u.get("home", f"/home/{username}")
        if username == "root":
            return "/root"
        return f"/home/{username}"

    def start(self) -> None:
        # Parse arguments
        login_shell = False
        run_command = None
        target_user = "root"  # default target is root
        preserve_env = False

        args = list(self.args)
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "-" or arg == "-l" or arg == "--login":
                login_shell = True
            elif arg == "-c" or arg == "--command":
                if i + 1 < len(args):
                    run_command = args[i + 1]
                    i += 1
                else:
                    self.errorWrite("su: option requires an argument -- 'c'\n")
                    self.exit()
                    return
            elif arg == "-s" or arg == "--shell":
                # Accept but ignore shell override
                if i + 1 < len(args):
                    i += 1
            elif arg == "-p" or arg == "--preserve-environment":
                preserve_env = True
            elif arg == "--help":
                self._show_help()
                return
            elif arg == "--version":
                self.write("su from util-linux 2.34\n")
                self.exit()
                return
            elif not arg.startswith("-"):
                target_user = arg
            i += 1

        # Check if user exists
        if not self._user_exists(target_user):
            self.errorWrite(f"su: user {target_user} does not exist\n")
            self.exit()
            return

        # Check if target user has a valid shell
        shell = self._get_user_shell(target_user)
        if shell in ("/usr/sbin/nologin", "/bin/false", "/sbin/nologin"):
            self.errorWrite(f"su: using restricted shell {shell}\n")
            self.write("This account is currently not available.\n")
            self.exit()
            return

        self._target_user = target_user
        self._login_shell = login_shell
        self._run_command = run_command

        # Determine current user
        current_user = getattr(self.protocol, "user", None)
        current_username = "root"
        if current_user:
            current_username = getattr(current_user, "username", "root")
            if isinstance(current_username, bytes):
                current_username = current_username.decode("utf-8", errors="replace")

        if current_username == "root":
            # Root doesn't need a password
            self._switch_user()
        else:
            # Non-root: ask for password
            self.write("Password: ")
            self.protocol.password_input = True
            self.callbacks = [self._check_password]

    def _check_password(self, line: str) -> None:
        """Handle password input."""
        self.protocol.password_input = False

        log.msg(
            eventid="cowrie.command.success",
            realm="su",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )

        # Always accept the password (simulating a successful su)
        # In a real scenario, we could check against profile passwords
        self._switch_user()

    def _get_user_uid_gid(self, username: str) -> tuple[int, int]:
        """Get uid/gid for a user from profile."""
        for u in self._get_profile_users():
            if u["name"] == username:
                return (u.get("uid", 1000), u.get("gid", 1000))
        if username == "root":
            return (0, 0)
        return (1000, 1000)

    def _switch_user(self) -> None:
        """Perform the user switch."""
        target = self._target_user
        home = self._get_user_home(target)
        uid, gid = self._get_user_uid_gid(target)

        self.protocol.switch_user(target, uid, gid, home)

        if self._login_shell:
            self.protocol.cwd = home
            if not self.protocol.fs.exists(self.protocol.cwd):
                self.protocol.cwd = "/"

        self.exit()

    def _show_help(self) -> None:
        self.write(
            """Usage:
 su [options] [-] [<user> [<argument>...]]

Change the effective user ID and group ID to that of <user>.
A mere - implies -l.  If <user> is not given, root is assumed.

Options:
 -m, -p, --preserve-environment  do not reset environment variables
 -g, --group <group>             specify the primary group
 -G, --supp-group <group>        specify a supplemental group
 -, -l, --login                  make the shell a login shell
 -c, --command <command>         pass a single command to the shell with -c
 -f, --fast                      pass -f to the shell (for csh or tcsh)
 -s, --shell <shell>             run <shell> if /etc/shells allows it
 -P, --pty                       create a new pseudo-terminal

 -h, --help                      display this help
 -V, --version                   display version
"""
        )
        self.exit()

    def lineReceived(self, line: str) -> None:
        log.msg(
            eventid="cowrie.command.success",
            realm="su",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )
        self.callbacks.pop(0)(line)


commands["/bin/su"] = Command_su
commands["su"] = Command_su
