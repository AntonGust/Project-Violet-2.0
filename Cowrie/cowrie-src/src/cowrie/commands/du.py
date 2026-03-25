# Copyright (c) 2018 Danilo Vargas <danilo.vargas@csiete.org>
# See the COPYRIGHT file for more information

from __future__ import annotations

import os

from cowrie.shell.command import HoneyPotCommand
from cowrie.shell.fs import A_CONTENTS, A_NAME, A_SIZE, A_TYPE, T_DIR, T_FILE, T_LINK, FileNotFound

commands = {}


class Command_du(HoneyPotCommand):
    def message_help(self) -> str:
        return """Usage: du [OPTION]... [FILE]...
  or:  du [OPTION]... --files0-from=F
Summarize disk usage of the set of FILEs, recursively for directories.

Mandatory arguments to long options are mandatory for short options too.
  -0, --null            end each output line with NUL, not newline
  -a, --all             write counts for all files, not just directories
      --apparent-size   print apparent sizes, rather than disk usage; although
                          the apparent size is usually smaller, it may be
                          larger due to holes in ('sparse') files, internal
                          fragmentation, indirect blocks, and the like
  -B, --block-size=SIZE  scale sizes by SIZE before printing them; e.g.,
                           '-BM' prints sizes in units of 1,048,576 bytes;
                           see SIZE format below
  -b, --bytes           equivalent to '--apparent-size --block-size=1'
  -c, --total           produce a grand total
  -D, --dereference-args  dereference only symlinks that are listed on the
                          command line
  -d, --max-depth=N     print the total for a directory (or file, with --all)
                          only if it is N or fewer levels below the command
                          line argument;  --max-depth=0 is the same as
                          --summarize
      --files0-from=F   summarize disk usage of the
                          NUL-terminated file names specified in file F;
                          if F is -, then read names from standard input
  -H                    equivalent to --dereference-args (-D)
  -h, --human-readable  print sizes in human readable format (e.g., 1K 234M 2G)
      --inodes          list inode usage information instead of block usage
  -k                    like --block-size=1K
  -L, --dereference     dereference all symbolic links
  -l, --count-links     count sizes many times if hard linked
  -m                    like --block-size=1M
  -P, --no-dereference  don't follow any symbolic links (this is the default)
  -S, --separate-dirs   for directories do not include size of subdirectories
      --si              like -h, but use powers of 1000 not 1024
  -s, --summarize       display only a total for each argument
  -t, --threshold=SIZE  exclude entries smaller than SIZE if positive,
                          or entries greater than SIZE if negative
      --time            show time of the last modification of any file in the
                          directory, or any of its subdirectories
      --time=WORD       show time as WORD instead of modification time:
                          atime, access, use, ctime or status
      --time-style=STYLE  show times using STYLE, which can be:
                            full-iso, long-iso, iso, or +FORMAT;
                            FORMAT is interpreted like in 'date'
  -X, --exclude-from=FILE  exclude files that match any pattern in FILE
      --exclude=PATTERN    exclude files that match PATTERN
  -x, --one-file-system    skip directories on different file systems
      --help     display this help and exit
      --version  output version information and exit

Display values are in units of the first available SIZE from --block-size,
and the DU_BLOCK_SIZE, BLOCK_SIZE and BLOCKSIZE environment variables.
Otherwise, units default to 1024 bytes (or 512 if POSIXLY_CORRECT is set).

The SIZE argument is an integer and optional unit (example: 10K is 10*1024).
Units are K,M,G,T,P,E,Z,Y (powers of 1024) or KB,MB,... (powers of 1000).

GNU coreutils online help: <http://www.gnu.org/software/coreutils/>
Report du translation bugs to <http://translationproject.org/team/>
Full documentation at: <http://www.gnu.org/software/coreutils/du>
or available locally via: info '(coreutils) du invocation'\n"""

    @staticmethod
    def _human_size(nbytes: int) -> str:
        for unit in ("", "K", "M", "G", "T"):
            if abs(nbytes) < 1024:
                if unit == "":
                    return f"{nbytes}"
                return f"{nbytes:.1f}{unit}" if nbytes != int(nbytes) else f"{int(nbytes)}{unit}"
            nbytes /= 1024
        return f"{nbytes:.1f}P"

    def _dir_size(self, path: str) -> int:
        """Recursively sum A_SIZE for all files under path."""
        total = 4096  # directory entry itself
        try:
            entries = self.protocol.fs.get_path(path)
        except (FileNotFound, Exception):
            return total
        for entry in entries:
            if entry[A_TYPE] == T_DIR:
                total += self._dir_size(os.path.join(path, entry[A_NAME]))
            elif entry[A_TYPE] in (T_FILE, T_LINK):
                total += entry[A_SIZE] if entry[A_SIZE] else 0
        return total

    def call(self) -> None:
        summary = False
        human = False
        show_total = False
        targets: list[str] = []

        for arg in self.args:
            if arg == "--help":
                self.write(self.message_help())
                return
            elif arg.startswith("-") and not arg.startswith("--"):
                for ch in arg[1:]:
                    if ch == "s":
                        summary = True
                    elif ch == "h":
                        human = True
                    elif ch == "c":
                        show_total = True
                    elif ch == "a":
                        pass  # show all files (we'll approximate)
            else:
                targets.append(arg)

        if not targets:
            targets = ["."]

        grand_total = 0
        for target in targets:
            resolved = self.fs.resolve_path(target, self.protocol.cwd)
            if not self.fs.exists(resolved):
                self.errorWrite(f"du: cannot access '{target}': No such file or directory\n")
                continue

            if self.fs.isdir(resolved):
                size = self._dir_size(resolved)
                if summary:
                    sz = self._human_size(size) if human else str(size // 1024)
                    self.write(f"{sz}\t{target}\n")
                else:
                    # Show subdirectories
                    try:
                        entries = self.fs.get_path(resolved)
                    except Exception:
                        entries = []
                    for entry in entries:
                        if entry[A_TYPE] == T_DIR:
                            child_path = os.path.join(resolved, entry[A_NAME])
                            child_display = os.path.join(target, entry[A_NAME])
                            child_size = self._dir_size(child_path)
                            sz = self._human_size(child_size) if human else str(child_size // 1024)
                            self.write(f"{sz}\t{child_display}\n")
                    sz = self._human_size(size) if human else str(size // 1024)
                    self.write(f"{sz}\t{target}\n")
                grand_total += size
            else:
                f = self.fs.getfile(resolved)
                size = f[A_SIZE] if f and f[A_SIZE] else 0
                sz = self._human_size(size) if human else str(size // 1024)
                self.write(f"{sz}\t{target}\n")
                grand_total += size

        if show_total:
            sz = self._human_size(grand_total) if human else str(grand_total // 1024)
            self.write(f"{sz}\ttotal\n")


commands["du"] = Command_du
