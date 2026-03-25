"""
head and tail command handlers for Cowrie honeypot.

Uses the same filesystem access pattern as cat.py — resolves paths against
the pickle filesystem and reads content from honeyfs.
"""

from __future__ import annotations

from typing import Any

from twisted.python import log

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.fs import FileNotFound

commands = {}


class Command_head(HoneyPotCommand):
    def start(self) -> None:
        num_lines = 10
        files: list[str] = []
        quiet = False

        i = 0
        while i < len(self.args):
            arg = self.args[i]
            if arg == "-n" and i + 1 < len(self.args):
                try:
                    num_lines = int(self.args[i + 1])
                except ValueError:
                    self.errorWrite(f"head: invalid number of lines: '{self.args[i + 1]}'\n")
                    self.exit()
                    return
                i += 2
                continue
            elif arg.startswith("-n"):
                try:
                    num_lines = int(arg[2:])
                except ValueError:
                    self.errorWrite(f"head: invalid number of lines: '{arg[2:]}'\n")
                    self.exit()
                    return
            elif arg.startswith("-") and arg[1:].isdigit():
                num_lines = int(arg[1:])
            elif arg == "-q":
                quiet = True
            elif arg in ("--help",):
                self.write("Usage: head [OPTION]... [FILE]...\n")
                self.write("Print the first 10 lines of each FILE to standard output.\n")
                self.exit()
                return
            elif arg == "-":
                if self.input_data is not None:
                    self._output_lines(self.input_data, num_lines)
            else:
                files.append(arg)
            i += 1

        if files:
            show_header = len(files) > 1 and not quiet
            for fname in files:
                pname = self.fs.resolve_path(fname, self.protocol.cwd)
                if self.fs.isdir(pname):
                    self.errorWrite(f"head: error reading '{fname}': Is a directory\n")
                    continue
                try:
                    contents = self.fs.file_contents(pname)
                    if show_header:
                        self.write(f"==> {fname} <==\n")
                    self._output_lines(contents, num_lines)
                except (FileNotFound, FileNotFoundError):
                    self.errorWrite(f"head: cannot open '{fname}' for reading: No such file or directory\n")
            self.exit()
        elif self.input_data is not None:
            self._output_lines(self.input_data, num_lines)
            self.exit()
        else:
            # No files and no pipe — wait for stdin (like real head)
            pass

    def _output_lines(self, data: bytes | None, n: int) -> None:
        if data is None:
            return
        lines = data.split(b"\n")
        for line in lines[:n]:
            self.writeBytes(line + b"\n")

    def lineReceived(self, line: str) -> None:
        log.msg(
            eventid="cowrie.session.input",
            realm="head",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )

    def handle_CTRL_D(self) -> None:
        self.exit()


commands["/usr/bin/head"] = Command_head
commands["head"] = Command_head


class Command_tail(HoneyPotCommand):
    callbacks: list[Any]

    def start(self) -> None:
        num_lines = 10
        follow = False
        files: list[str] = []
        quiet = False

        i = 0
        while i < len(self.args):
            arg = self.args[i]
            if arg == "-n" and i + 1 < len(self.args):
                try:
                    num_lines = int(self.args[i + 1])
                except ValueError:
                    self.errorWrite(f"tail: invalid number of lines: '{self.args[i + 1]}'\n")
                    self.exit()
                    return
                i += 2
                continue
            elif arg.startswith("-n"):
                try:
                    num_lines = int(arg[2:])
                except ValueError:
                    self.errorWrite(f"tail: invalid number of lines: '{arg[2:]}'\n")
                    self.exit()
                    return
            elif arg == "-f" or arg == "--follow":
                follow = True
            elif arg.startswith("-") and arg[1:].isdigit():
                num_lines = int(arg[1:])
            elif arg == "-q":
                quiet = True
            elif arg in ("--help",):
                self.write("Usage: tail [OPTION]... [FILE]...\n")
                self.write("Print the last 10 lines of each FILE to standard output.\n")
                self.exit()
                return
            elif arg == "-":
                if self.input_data is not None:
                    self._output_tail(self.input_data, num_lines)
            else:
                files.append(arg)
            i += 1

        if files:
            show_header = len(files) > 1 and not quiet
            for fname in files:
                pname = self.fs.resolve_path(fname, self.protocol.cwd)
                if self.fs.isdir(pname):
                    self.errorWrite(f"tail: error reading '{fname}': Is a directory\n")
                    continue
                try:
                    contents = self.fs.file_contents(pname)
                    if show_header:
                        self.write(f"==> {fname} <==\n")
                    self._output_tail(contents, num_lines)
                except (FileNotFound, FileNotFoundError):
                    self.errorWrite(f"tail: cannot open '{fname}' for reading: No such file or directory\n")

            if follow:
                # Simulate tail -f: print content then hang until Ctrl-C
                self.callbacks = [self._ignore_input]
                return
            self.exit()
        elif self.input_data is not None:
            self._output_tail(self.input_data, num_lines)
            self.exit()
        else:
            pass

    def _output_tail(self, data: bytes | None, n: int) -> None:
        if data is None:
            return
        lines = data.split(b"\n")
        # Remove trailing empty line from final newline
        if lines and lines[-1] == b"":
            lines = lines[:-1]
        tail_lines = lines[-n:] if n <= len(lines) else lines
        for line in tail_lines:
            self.writeBytes(line + b"\n")

    def _ignore_input(self, line: str) -> None:
        """Absorb input while in follow mode."""
        pass

    def lineReceived(self, line: str) -> None:
        log.msg(
            eventid="cowrie.session.input",
            realm="tail",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )
        if hasattr(self, "callbacks") and self.callbacks:
            self.callbacks[0](line)

    def handle_CTRL_C(self) -> None:
        self.exit()

    def handle_CTRL_D(self) -> None:
        self.exit()


commands["/usr/bin/tail"] = Command_tail
commands["tail"] = Command_tail
