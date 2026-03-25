# Copyright (c) 2015 Michel Oosterhof <michel@oosterhof.net>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. The names of the author(s) may not be used to endorse or promote
#    products derived from this software without specific prior written
#    permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHORS ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
# OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.

from __future__ import annotations

import getopt
import hashlib
import json
import os
import re
import time

from twisted.python import log

from cowrie.core.config import CowrieConfig
from cowrie.shell import fs
from cowrie.shell.command import HoneyPotCommand

commands = {}


class Command_scp(HoneyPotCommand):
    """
    scp command
    """

    download_path = CowrieConfig.get("honeypot", "download_path", fallback=".")
    download_path_uniq = CowrieConfig.get(
        "honeypot", "download_path_uniq", fallback=download_path
    )

    out_dir: str = ""

    def help(self) -> None:
        self.write(
            """usage: scp [-12346BCpqrv] [-c cipher] [-F ssh_config] [-i identity_file]
           [-l limit] [-o ssh_option] [-P port] [-S program]
           [[user@]host1:]file1 ... [[user@]host2:]file2\n"""
        )

    def start(self) -> None:
        try:
            optlist, args = getopt.getopt(self.args, "12346BCpqrvfstdv:cFiloPS:")
        except getopt.GetoptError:
            self.help()
            self.exit()
            return

        self.out_dir = ""

        for opt in optlist:
            if opt[0] == "-d":
                self.out_dir = args[0]
                break
            if opt[0] == "-f":
                # Pull mode: honeypot sends file to SCP client
                self._handle_pull(args)
                return

        # Detect remote args: scan ALL args for [user@]host:path
        remote_re = re.compile(r"^(?:\S+@)?[\w.\-]+:.+$")
        remote_indices = [i for i, a in enumerate(args) if remote_re.match(a)]

        if remote_indices:
            if remote_indices[-1] == len(args) - 1:
                # Remote is last arg → push (local → remote)
                self._handle_outbound(args)
            else:
                # Remote is not last arg → pull (remote → local)
                self._handle_pull_remote(args, remote_indices)
            return

        if self.out_dir:
            outdir = self.fs.resolve_path(self.out_dir, self.protocol.cwd)

            if not self.fs.exists(outdir):
                self.errorWrite(f"-scp: {self.out_dir}: No such file or directory\n")
                self.exit()

        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")
        self.write("\x00")

    def _handle_outbound(self, args: list[str]) -> None:
        """Simulate outbound scp transfer."""
        source_files = args[:-1]
        for src in source_files:
            resolved = self.fs.resolve_path(src, self.protocol.cwd)
            if not self.fs.exists(resolved):
                self.errorWrite(f"scp: {src}: No such file or directory\n")
                self.exit()
                return
            try:
                st = self.fs.stat(resolved)
                size = st.st_size
            except Exception:
                size = 4096
            fname = os.path.basename(src)
            self.write(f"{fname}                                      100% {size:>5}     {size / 1024:.1f}KB/s   00:00\n")
        self.exit()

    def _load_remote_files_index(self) -> dict:
        """Load the remote files index from etc/remote_files.json."""
        try:
            contents_path = CowrieConfig.get(
                "honeypot", "contents_path", fallback="honeyfs"
            )
            index_path = os.path.join(
                os.path.dirname(contents_path), "etc", "remote_files.json"
            )
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _handle_pull_remote(self, args: list[str], remote_indices: list[int]) -> None:
        """Simulate pulling files from a remote host.

        Checks the remote_files index for real content deployed by the
        profile converter.  Falls back to a stub file if no content exists.
        Unknown hosts get a fast 'Connection refused' instead of hanging.
        """
        # Determine local destination (last non-remote arg)
        local_dest = args[-1] if len(args) > 1 else "."

        # Resolve the destination directory
        dest_resolved = self.fs.resolve_path(local_dest, self.protocol.cwd)

        # Collect known hosts from /etc/hosts for realism check
        known_hosts: set[str] = set()
        try:
            hosts_bytes = self.fs.file_contents("/etc/hosts")
            for line in hosts_bytes.decode("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts:
                    known_hosts.add(parts[0])          # IP address
                    known_hosts.update(parts[1:])      # hostnames
        except Exception:
            pass

        # Load remote files index for real content
        remote_index = self._load_remote_files_index()
        contents_path = CowrieConfig.get(
            "honeypot", "contents_path", fallback="honeyfs"
        )

        for idx in remote_indices:
            remote_arg = args[idx]

            # Parse user@host:path or host:path
            m = re.match(r"^(?:(\S+)@)?([\w.\-]+):(.+)$", remote_arg)
            if not m:
                self.errorWrite(f"scp: {remote_arg}: invalid remote specification\n")
                self.exit()
                return

            user = m.group(1) or "root"
            host = m.group(2)
            remote_path = m.group(3)

            # Unknown host → connection refused (fast fail, no hang)
            if host not in known_hosts:
                self.errorWrite(
                    f"ssh: connect to host {host} port 22: Connection refused\n"
                )
                self.exit()
                return

            fname = os.path.basename(remote_path)

            # Check remote files index for real content
            host_files = remote_index.get(host, {})
            file_meta = host_files.get(remote_path, {})
            file_size = file_meta.get("size", 4096)
            honeyfs_rel = file_meta.get("honeyfs_path", "")

            # Read content from honeyfs if available
            content = None
            if honeyfs_rel:
                real_path = os.path.join(contents_path, honeyfs_rel)
                try:
                    with open(real_path, "rb") as fh:
                        content = fh.read()
                    file_size = len(content)
                except Exception:
                    pass

            # Simulate progress bar output (matches real SCP output format)
            if file_size >= 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f}MB"
                speed_str = f"{file_size / (1024 * 1024 * 2):.1f}MB/s"
            else:
                size_str = f"{file_size}"
                speed_str = f"{file_size / 1024:.1f}KB/s"
            self.write(
                f"{fname:<42s} 100% {size_str:>7}     "
                f"{speed_str}   00:00\n"
            )

            # Create file in VFS
            if self.fs.exists(dest_resolved) and self.fs.isdir(dest_resolved):
                outfile = os.path.join(dest_resolved, fname)
            else:
                outfile = dest_resolved

            try:
                self.fs.mkfile(
                    outfile,
                    self.protocol.user.uid,
                    self.protocol.user.gid,
                    file_size,
                    33188,  # 0o100644 — regular file, rw-r--r--
                )
            except Exception:
                pass

            # If we have real content, set the realfile pointer so cat works
            if content and honeyfs_rel:
                real_path = os.path.join(contents_path, honeyfs_rel)
                try:
                    f = self.fs.getfile(outfile)
                    if f:
                        f[fs.A_REALFILE] = real_path
                except Exception:
                    pass

        self.exit()

    def _handle_pull(self, args: list[str]) -> None:
        """Handle SCP pull mode (-f): serve a file from the virtual filesystem."""
        if not args:
            self.write("\x01scp: missing file operand\n")
            self.exit()
            return

        file_path = args[0]
        resolved = self.fs.resolve_path(file_path, self.protocol.cwd)

        if not self.fs.exists(resolved):
            self.write(f"\x01scp: {file_path}: No such file or directory\n")
            self.exit()
            return

        f = self.fs.getfile(resolved)
        if f[fs.A_TYPE] == fs.T_DIR:
            self.write(f"\x01scp: {file_path}: not a regular file\n")
            self.exit()
            return

        # Try to read file content from honeyfs or realfile
        content = b""
        real_path = self.fs.realfile(f, resolved)
        if real_path:
            try:
                with open(real_path, "rb") as fh:
                    content = fh.read()
            except Exception:
                pass

        fname = os.path.basename(file_path)
        size = len(content)

        # SCP protocol: send header, content, then success marker
        self.writeBytes(f"C0644 {size} {fname}\n".encode())
        if content:
            self.writeBytes(content)
        self.writeBytes(b"\x00")
        self.exit()

    def lineReceived(self, line: str) -> None:
        log.msg(
            eventid="cowrie.session.file_download",
            realm="scp",
            input=line,
            format="INPUT (%(realm)s): %(input)s",
        )
        self.protocol.terminal.write("\x00")

    def drop_tmp_file(self, data: bytes, name: str) -> None:
        tmp_fname = "{}-{}-{}-scp_{}".format(
            time.strftime("%Y%m%d-%H%M%S"),
            self.protocol.getProtoTransport().transportId,
            self.protocol.terminal.transport.session.id,
            re.sub("[^A-Za-z0-9]", "_", name),
        )

        self.safeoutfile = os.path.join(self.download_path, tmp_fname)

        with open(self.safeoutfile, "wb+") as f:
            f.write(data)

    def save_file(self, data: bytes, fname: str) -> None:
        self.drop_tmp_file(data, fname)

        if os.path.exists(self.safeoutfile):
            with open(self.safeoutfile, "rb"):
                shasum = hashlib.sha256(data).hexdigest()
                hash_path = os.path.join(self.download_path_uniq, shasum)

            # If we have content already, delete temp file
            if not os.path.exists(hash_path):
                os.rename(self.safeoutfile, hash_path)
                duplicate = False
            else:
                os.remove(self.safeoutfile)
                duplicate = True

            log.msg(
                format='SCP Uploaded file "%(filename)s" to %(outfile)s',
                eventid="cowrie.session.file_upload",
                filename=os.path.basename(fname),
                duplicate=duplicate,
                url=fname,
                outfile=shasum,
                shasum=shasum,
                destfile=fname,
            )

            # Update the honeyfs to point to downloaded file
            self.fs.update_realfile(self.fs.getfile(fname), hash_path)
            self.fs.chown(fname, self.protocol.user.uid, self.protocol.user.gid)

    def parse_scp_data(self, data: bytes) -> bytes:
        # scp data format:
        # C0XXX filesize filename\nfile_data\x00
        # 0XXX - file permissions
        # filesize - size of file in bytes in decimal notation

        pos = data.find(b"\n")
        if pos != -1:
            header = data[:pos]

            pos += 1

            if re.match(rb"^C0[\d]{3} [\d]+ [^\s]+$", header):
                r = re.search(rb"C(0[\d]{3}) ([\d]+) ([^\s]+)", header)

                if r and r.group(1) and r.group(2) and r.group(3):
                    dend = pos + int(r.group(2))

                    if dend > len(data):
                        dend = len(data)

                    d = data[pos:dend]

                    if self.out_dir:
                        fname = os.path.join(self.out_dir, r.group(3).decode())
                    else:
                        fname = r.group(3).decode()

                    outfile = self.fs.resolve_path(fname, self.protocol.cwd)

                    try:
                        self.fs.mkfile(
                            outfile,
                            self.protocol.user.uid,
                            self.protocol.user.gid,
                            r.group(2),
                            r.group(1),
                        )
                    except fs.FileNotFound:
                        # The outfile locates at a non-existing directory.
                        self.errorWrite(f"-scp: {outfile}: No such file or directory\n")
                        return b""

                    self.save_file(d, outfile)

                    data = data[dend + 1 :]  # cut saved data + \x00
            else:
                data = b""
        else:
            data = b""

        return data

    def handle_CTRL_D(self) -> None:
        if (
            self.protocol.terminal.stdinlogOpen
            and self.protocol.terminal.stdinlogFile
            and os.path.exists(self.protocol.terminal.stdinlogFile)
        ):
            with open(self.protocol.terminal.stdinlogFile, "rb") as f:
                data: bytes = f.read()
                header: bytes = data[: data.find(b"\n")]
                if re.match(rb"C0[\d]{3} [\d]+ [^\s]+", header):
                    content = data[data.find(b"\n") + 1 :]
                else:
                    content = b""

            if content:
                with open(self.protocol.terminal.stdinlogFile, "wb") as f:
                    f.write(content)

        self.exit()


commands["/usr/bin/scp"] = Command_scp
commands["scp"] = Command_scp
