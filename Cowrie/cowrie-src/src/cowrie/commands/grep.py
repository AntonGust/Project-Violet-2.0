"""
Filesystem-aware grep command handler for Cowrie honeypot.

Searches actual file contents from the pickle filesystem / honeyfs,
so results are consistent with cat, head, tail, and ls.
"""

from __future__ import annotations

import fnmatch
import getopt
import os
import re

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.fs import A_CONTENTS, A_NAME, A_TYPE, T_DIR, T_FILE, T_LINK, FileNotFound

commands = {}


class Command_grep(HoneyPotCommand):
    def call(self) -> None:
        # Parse flags
        try:
            optlist, args = getopt.gnu_getopt(
                self.args, "rilnchHvwe:E:",
                ["recursive", "ignore-case", "files-with-matches",
                 "line-number", "count", "no-filename", "with-filename",
                 "invert-match", "word-regexp", "include=", "exclude=",
                 "help", "version", "color=", "colour="],
            )
        except getopt.GetoptError as err:
            self.errorWrite(f"grep: {err}\n")
            self.exit()
            return

        ignore_case = False
        recursive = False
        files_only = False
        line_numbers = False
        count_mode = False
        show_filename = None  # None = auto
        invert = False
        word_regexp = False
        pattern_str = None
        include_glob = None
        exclude_glob = None

        for o, a in optlist:
            if o in ("-i", "--ignore-case"):
                ignore_case = True
            elif o in ("-r", "-R", "--recursive"):
                recursive = True
            elif o in ("-l", "--files-with-matches"):
                files_only = True
            elif o in ("-n", "--line-number"):
                line_numbers = True
            elif o in ("-c", "--count"):
                count_mode = True
            elif o in ("-H", "--with-filename"):
                show_filename = True
            elif o in ("-h", "--no-filename"):
                show_filename = False
            elif o in ("-v", "--invert-match"):
                invert = True
            elif o in ("-w", "--word-regexp"):
                word_regexp = True
            elif o in ("-e", "-E"):
                pattern_str = a
            elif o == "--include":
                include_glob = a
            elif o == "--exclude":
                exclude_glob = a
            elif o == "--help":
                self.write("Usage: grep [OPTION]... PATTERN [FILE]...\n")
                self.write("Search for PATTERN in each FILE.\n")
                return
            elif o == "--version":
                self.write("grep (GNU grep) 3.7\n")
                return

        if pattern_str is None:
            if not args:
                self.errorWrite("grep: missing pattern\n")
                return
            pattern_str = args.pop(0)

        # Compile pattern
        flags = re.IGNORECASE if ignore_case else 0
        if word_regexp:
            pattern_str = r"\b" + pattern_str + r"\b"
        try:
            pat = re.compile(pattern_str, flags)
        except re.error:
            # Fall back to literal match
            pat = re.compile(re.escape(pattern_str), flags)

        # Determine targets
        targets = args if args else ["-"]

        if targets == ["-"] and self.input_data is not None:
            # Piped input
            self._grep_bytes(pat, self.input_data, "(standard input)",
                             show_filename=False, line_numbers=line_numbers,
                             count_mode=count_mode, files_only=files_only,
                             invert=invert)
            return

        if targets == ["-"]:
            # No files, no pipe
            self.errorWrite("grep: missing file operand\n")
            return

        # Auto-detect filename display
        if show_filename is None:
            show_filename = len(targets) > 1 or recursive

        for target in targets:
            resolved = self.fs.resolve_path(target, self.protocol.cwd)

            if self.fs.isdir(resolved):
                if recursive:
                    self._grep_recursive(pat, resolved, target,
                                         show_filename=show_filename,
                                         line_numbers=line_numbers,
                                         count_mode=count_mode,
                                         files_only=files_only,
                                         invert=invert,
                                         include_glob=include_glob,
                                         exclude_glob=exclude_glob)
                else:
                    self.errorWrite(f"grep: {target}: Is a directory\n")
            elif self.fs.exists(resolved):
                self._grep_file(pat, resolved, target,
                                show_filename=show_filename,
                                line_numbers=line_numbers,
                                count_mode=count_mode,
                                files_only=files_only,
                                invert=invert)
            else:
                self.errorWrite(f"grep: {target}: No such file or directory\n")

    def _grep_file(self, pat, resolved_path: str, display_path: str, **kwargs) -> None:
        try:
            contents = self.fs.file_contents(resolved_path)
        except (FileNotFound, FileNotFoundError, IsADirectoryError):
            return
        self._grep_bytes(pat, contents, display_path, **kwargs)

    def _grep_bytes(self, pat, data: bytes, filename: str, *,
                    show_filename: bool, line_numbers: bool,
                    count_mode: bool, files_only: bool,
                    invert: bool) -> None:
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return

        lines = text.split("\n")
        match_count = 0

        for i, line in enumerate(lines, 1):
            matched = bool(pat.search(line))
            if invert:
                matched = not matched
            if matched:
                match_count += 1
                if files_only:
                    self.write(f"{filename}\n")
                    return
                if not count_mode:
                    prefix = ""
                    if show_filename:
                        prefix += f"{filename}:"
                    if line_numbers:
                        prefix += f"{i}:"
                    self.write(f"{prefix}{line}\n")

        if count_mode:
            if show_filename:
                self.write(f"{filename}:{match_count}\n")
            else:
                self.write(f"{match_count}\n")

    def _grep_recursive(self, pat, resolved_dir: str, display_dir: str, *,
                        include_glob, exclude_glob, **kwargs) -> None:
        """Walk the pickle filesystem recursively and grep each file."""
        try:
            entries = self.fs.get_path(resolved_dir)
        except (FileNotFound, FileNotFoundError):
            return

        for entry in entries:
            name = entry[A_NAME]
            child_resolved = os.path.join(resolved_dir, name)
            child_display = os.path.join(display_dir, name)

            if entry[A_TYPE] == T_DIR:
                self._grep_recursive(pat, child_resolved, child_display,
                                     include_glob=include_glob,
                                     exclude_glob=exclude_glob, **kwargs)
            elif entry[A_TYPE] in (T_FILE, T_LINK):
                if include_glob and not fnmatch.fnmatch(name, include_glob):
                    continue
                if exclude_glob and fnmatch.fnmatch(name, exclude_glob):
                    continue
                self._grep_file(pat, child_resolved, child_display, **kwargs)


commands["/usr/bin/grep"] = Command_grep
commands["/bin/grep"] = Command_grep
commands["grep"] = Command_grep
