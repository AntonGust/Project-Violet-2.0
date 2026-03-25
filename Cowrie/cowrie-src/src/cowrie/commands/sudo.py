from __future__ import annotations
import getopt
from typing import Any

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.pipe import PipeProtocol

commands = {}

sudo_shorthelp = (
    (
        """
sudo: Only one of the -e, -h, -i, -K, -l, -s, -v or -V options may be specified
usage: sudo [-D level] -h | -K | -k | -V
usage: sudo -v [-AknS] [-D level] [-g groupname|#gid] [-p prompt] [-u user name|#uid]
usage: sudo -l[l] [-AknS] [-D level] [-g groupname|#gid] [-p prompt] [-U user name] [-u user name|#uid] [-g groupname|#gid] [command]
usage: sudo [-AbEHknPS] [-r role] [-t type] [-C fd] [-D level] [-g groupname|#gid] [-p prompt] [-u user name|#uid] [-g groupname|#gid] [VAR=value] [-i|-s] [<command>]
usage: sudo -e [-AknS] [-r role] [-t type] [-C fd] [-D level] [-g groupname|#gid] [-p prompt] [-u user name|#uid] file ...
"""
    )
    .strip()
    .split("\n")
)

sudo_longhelp = (
    (
        """
sudo - execute a command as another user

usage: sudo [-D level] -h | -K | -k | -V
usage: sudo -v [-AknS] [-D level] [-g groupname|#gid] [-p prompt] [-u user name|#uid]
usage: sudo -l[l] [-AknS] [-D level] [-g groupname|#gid] [-p prompt] [-U user name] [-u user name|#uid] [-g groupname|#gid] [command]
usage: sudo [-AbEHknPS] [-r role] [-t type] [-C fd] [-D level] [-g groupname|#gid] [-p prompt] [-u user name|#uid] [-g groupname|#gid] [VAR=value] [-i|-s] [<command>]
usage: sudo -e [-AknS] [-r role] [-t type] [-C fd] [-D level] [-g groupname|#gid] [-p prompt] [-u user name|#uid] file ...

Options:
  -a type       use specified BSD authentication type
  -b            run command in the background
  -C fd         close all file descriptors >= fd
  -E            preserve user environment when executing command
  -e            edit files instead of running a command
  -g group      execute command as the specified group
  -H            set HOME variable to target user's home dir.
  -h            display help message and exit
  -i [command]  run a login shell as target user
  -K            remove timestamp file completely
  -k            invalidate timestamp file
  -l[l] command list user's available commands
  -n            non-interactive mode, will not prompt user
  -P            preserve group vector instead of setting to target's
  -p prompt     use specified password prompt
  -r role       create SELinux security context with specified role
  -S            read password from standard input
  -s [command]  run a shell as target user
  -t type       create SELinux security context with specified role
  -U user       when listing, list specified user's privileges
  -u user       run command (or edit file) as specified user
  -V            display version information and exit
  -v            update user's timestamp without running a command
  --            stop processing command line arguments
"""
    )
    .strip()
    .split("\n")
)


class Command_sudo(HoneyPotCommand):
    def short_help(self) -> None:
        for ln in sudo_shorthelp:
            self.errorWrite(f"{ln}\n")
        self.exit()

    def long_help(self) -> None:
        for ln in sudo_longhelp:
            self.errorWrite(f"{ln}\n")
        self.exit()

    def version(self) -> None:
        self.errorWrite(
            """Sudo version 1.8.5p2
            Sudoers policy plugin version 1.8.5p2
            Sudoers file grammar version 41
            Sudoers I/O plugin version 1.8.5p2\n"""
        )
        self.exit()

    def _get_profile_users(self) -> list[dict[str, Any]]:
        """Get user list from profile."""
        handler = getattr(self.protocol, "llm_fallback_handler", None)
        if handler is None:
            return []
        profile = getattr(handler, "_profile", {})
        return profile.get("users", [])

    def _resolve_target_user(self, target_user: str | None) -> tuple[str, int, int, str]:
        """Resolve target user to (username, uid, gid, home). Defaults to root."""
        username = target_user or "root"
        if username == "root":
            return ("root", 0, 0, "/root")
        for u in self._get_profile_users():
            if u["name"] == username:
                return (username, u.get("uid", 1000), u.get("gid", 1000), u.get("home", f"/home/{username}"))
        return (username, 1000, 1000, f"/home/{username}")

    def list_privileges(self) -> None:
        """Handle sudo -l: list current user's sudo privileges."""
        current_user = "root"
        user_obj = getattr(self.protocol, "user", None)
        if user_obj:
            uname = getattr(user_obj, "username", "root")
            if isinstance(uname, bytes):
                uname = uname.decode("utf-8", errors="replace")
            current_user = uname

        # Find sudo_rules for this user from profile
        sudo_rules = None
        for u in self._get_profile_users():
            if u["name"] == current_user:
                sudo_rules = u.get("sudo_rules", "")
                break

        hostname = self.environ.get("HOSTNAME", "localhost")

        self.write(f"Matching Defaults entries for {current_user} on {hostname}:\n")
        self.write("    env_reset, mail_badpass,\n")
        self.write("    secure_path=/usr/local/sbin\\:/usr/local/bin\\:/usr/sbin\\:/usr/bin\\:/sbin\\:/bin\\:/snap/bin\n")
        self.write(f"\nUser {current_user} may run the following commands on {hostname}:\n")

        if current_user == "root":
            self.write("    (ALL : ALL) ALL\n")
        elif sudo_rules:
            # Parse rules like "deploy ALL=(ALL) NOPASSWD: ALL"
            # Strip the username prefix if present
            rule_body = sudo_rules
            if rule_body.startswith(current_user):
                rule_body = rule_body[len(current_user):].strip()
            self.write(f"    {rule_body}\n")
        else:
            self.write(f"    (sorry) {current_user} is not allowed to run sudo on {hostname}.\n")

        self.exit()

    def start(self) -> None:
        start_value = None
        parsed_arguments = []
        for count in range(0, len(self.args)):
            class_found = self.protocol.getCommand(
                self.args[count], self.environ["PATH"].split(":")
            )
            if class_found:
                start_value = count
                break
        if start_value is not None:
            for index_2 in range(start_value, len(self.args)):
                parsed_arguments.append(self.args[index_2])

        # Handle -l before getopt since it takes an optional argument
        # which getopt can't handle properly
        if self.args and self.args[0] in ("-l", "-ll"):
            self.list_privileges()
            return

        try:
            optlist, _args = getopt.getopt(
                self.args[0:start_value], "bEeHhiKknPsSVva:C:g:p:r:t:U:u:"
            )
        except getopt.GetoptError as err:
            self.errorWrite("sudo: illegal option -- " + err.opt + "\n")
            self.short_help()
            return

        target_user = None
        wants_shell = False
        for o, a in optlist:
            if o in ("-V"):
                self.version()
                return
            elif o in ("-h"):
                self.long_help()
                return
            elif o in ("-u"):
                target_user = a
            elif o in ("-i", "-s"):
                wants_shell = True

        if len(parsed_arguments) > 0:
            cmd = parsed_arguments[0]
            cmdclass = self.protocol.getCommand(cmd, self.environ["PATH"].split(":"))

            if cmdclass:
                # Switch to target user before running the command
                uname, uid, gid, home = self._resolve_target_user(target_user)
                self.protocol.switch_user(uname, uid, gid, home)

                # Propagate the outer pipe chain so sudo cmd | grep works
                outer_pp = getattr(self.protocol, "pp", None)
                next_cmd = outer_pp.next_command if outer_pp else None
                command = PipeProtocol(
                    self.protocol, cmdclass, parsed_arguments[1:], None, next_cmd
                )
                self.protocol.pp.insert_command(command)
                # this needs to go here so it doesn't write it out....
                if self.input_data:
                    self.writeBytes(self.input_data)
                self.exit()
            else:
                self.short_help()
        elif wants_shell:
            # sudo -i or sudo -s: switch to target user and stay in shell
            uname, uid, gid, home = self._resolve_target_user(target_user)
            self.protocol.switch_user(uname, uid, gid, home)
            self.protocol.cwd = home
            if not self.protocol.fs.exists(self.protocol.cwd):
                self.protocol.cwd = "/"
            self.exit()
        else:
            self.short_help()


commands["sudo"] = Command_sudo
