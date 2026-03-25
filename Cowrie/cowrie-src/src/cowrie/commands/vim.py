"""
vim and nano editor simulation for Cowrie honeypot.

Shows real file contents from honeyfs/pickle filesystem, then accepts
exit commands (:q, :wq for vim; Ctrl-C/Ctrl-D for nano). No actual
editing — attackers use editors to READ config files, which is the
critical part for honeypot authenticity.
"""

from __future__ import annotations

from typing import Any

from twisted.python import log

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.fs import FileNotFound

commands = {}


class Command_vim(HoneyPotCommand):
    callbacks: list[Any]

    def start(self) -> None:
        self._filename = ""

        # Extract filename from args (skip flags like -R, -r, +cmd)
        filepath = None
        for arg in self.args:
            if not arg.startswith("-") and not arg.startswith("+"):
                filepath = arg
                break

        if not filepath:
            self._show_splash()
            self.callbacks = [self._handle_input]
            return

        self._filename = filepath
        resolved = self.fs.resolve_path(filepath, self.protocol.cwd)

        if self.fs.isdir(resolved):
            self.errorWrite(f'"{filepath}" is a directory\n')
            self.exit()
            return

        try:
            contents = self.fs.file_contents(resolved)
            text = contents.decode("utf-8", errors="replace")
            self._display_vim(text, filepath)
        except (FileNotFound, FileNotFoundError):
            self._display_vim("", filepath, new_file=True)

        self.callbacks = [self._handle_input]

    def _show_splash(self) -> None:
        term_h = int(self.environ.get("LINES", 24))
        self.write("\n")
        top_pad = max(0, term_h // 3 - 2)
        for _ in range(top_pad):
            self.write("~\n")
        self.write("~                    VIM - Vi IMproved\n")
        self.write("~\n")
        self.write("~                     version 8.2\n")
        self.write("~                by Bram Moolenaar et al.\n")
        self.write("~\n")
        self.write("~            type  :q<Enter>          to exit\n")
        self.write("~            type  :help<Enter>       for on-line help\n")
        self.write("~\n")
        remaining = term_h - top_pad - 9
        for _ in range(max(0, remaining)):
            self.write("~\n")

    def _display_vim(self, text: str, filename: str, new_file: bool = False) -> None:
        term_h = int(self.environ.get("LINES", 24)) - 2  # status + command line
        lines = text.split("\n") if text else []

        # Show file content
        shown = 0
        for line in lines[:term_h]:
            self.write(line + "\n")
            shown += 1

        # Fill remaining with ~
        for _ in range(max(0, term_h - shown)):
            self.write("~\n")

        # Status line
        if new_file:
            self.write(f'"{filename}" [New File]\n')
        else:
            line_count = len(lines)
            char_count = len(text)
            self.write(f'"{filename}" {line_count}L, {char_count}C\n')

    def _handle_input(self, line: str) -> None:
        stripped = line.strip()

        log.msg(
            eventid="cowrie.command.input",
            realm="vim",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )

        if stripped in (":q", ":q!", ":wq", ":wq!", ":x", ":x!", "ZZ", ":qa", ":qa!", ":exit"):
            self.exit()
            return

        if stripped == ":w" or stripped.startswith(":w "):
            fname = self._filename or stripped[3:].strip() or "[No Name]"
            self.write(f'"{fname}" written\n')
            self.callbacks = [self._handle_input]
            return

        # Stay in editor for any other input
        self.callbacks = [self._handle_input]

    def lineReceived(self, line: str) -> None:
        if hasattr(self, "callbacks") and self.callbacks:
            self.callbacks.pop(0)(line)

    def handle_CTRL_C(self) -> None:
        self.write("Type  :qa!  to exit Vim\n")
        self.callbacks = [self._handle_input]

    def handle_CTRL_D(self) -> None:
        self.exit()


commands["/usr/bin/vim"] = Command_vim
commands["/usr/bin/vi"] = Command_vim
commands["vim"] = Command_vim
commands["vi"] = Command_vim


class Command_nano(HoneyPotCommand):
    callbacks: list[Any]

    def start(self) -> None:
        self._filename = ""

        filepath = None
        for arg in self.args:
            if not arg.startswith("-"):
                filepath = arg
                break

        if filepath:
            self._filename = filepath
            resolved = self.fs.resolve_path(filepath, self.protocol.cwd)

            if self.fs.isdir(resolved):
                self.errorWrite(f"Error reading {filepath}: Is a directory\n")
                self.exit()
                return

            try:
                contents = self.fs.file_contents(resolved)
                text = contents.decode("utf-8", errors="replace")
            except (FileNotFound, FileNotFoundError):
                text = ""  # New file
        else:
            text = ""
            filepath = "New Buffer"

        self._display_nano(text, filepath)
        self.callbacks = [self._handle_input]

    def _display_nano(self, text: str, filename: str) -> None:
        term_h = int(self.environ.get("LINES", 24)) - 5  # header + 2 footer lines + padding
        self.write(f"  GNU nano 5.4                    {filename}\n")
        self.write("\n")

        lines = text.split("\n") if text else []
        shown = 0
        for line in lines[:term_h]:
            self.write(line + "\n")
            shown += 1
        for _ in range(max(0, term_h - shown)):
            self.write("\n")

        self.write("\n")
        self.write("^G Get Help  ^O Write Out  ^W Where Is  ^K Cut Text   ^J Justify\n")
        self.write("^X Exit      ^R Read File  ^\\ Replace   ^U Paste Text ^T To Spell\n")

    def _handle_input(self, line: str) -> None:
        log.msg(
            eventid="cowrie.command.input",
            realm="nano",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )
        # Stay in editor
        self.callbacks = [self._handle_input]

    def lineReceived(self, line: str) -> None:
        if hasattr(self, "callbacks") and self.callbacks:
            self.callbacks.pop(0)(line)

    def handle_CTRL_C(self) -> None:
        # Ctrl-C in nano = cancel current operation; use as exit for honeypot
        self.exit()

    def handle_CTRL_D(self) -> None:
        self.exit()


commands["/usr/bin/nano"] = Command_nano
commands["nano"] = Command_nano
