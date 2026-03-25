from __future__ import annotations

import base64
import getopt
import os
import random
import struct
import time

from twisted.python import log

from cowrie.core.config import CowrieConfig
from cowrie.shell.command import HoneyPotCommand
from cowrie.shell import fs

commands = {}


def _random_bytes(n: int) -> bytes:
    return bytes(random.getrandbits(8) for _ in range(n))


def _fake_rsa_private_key(bits: int = 2048) -> str:
    """Generate a realistic-looking RSA private key in PEM format."""
    # Real RSA keys are ~1700 bytes for 2048-bit, ~3200 for 4096-bit
    byte_count = (bits // 8) * 2 + 128
    raw = _random_bytes(byte_count)
    b64 = base64.b64encode(raw).decode()
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN OPENSSH PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END OPENSSH PRIVATE KEY-----\n"


def _fake_rsa_public_key(bits: int = 2048, comment: str = "") -> str:
    """Generate a realistic-looking RSA public key."""
    # Build a fake SSH public key blob: string "ssh-rsa" + mpint e + mpint n
    key_type = b"ssh-rsa"
    e = b"\x01\x00\x01"  # 65537
    n = _random_bytes(bits // 8)

    def _pack(data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + data

    blob = _pack(key_type) + _pack(e) + _pack(b"\x00" + n)
    b64 = base64.b64encode(blob).decode()
    line = f"ssh-rsa {b64}"
    if comment:
        line += f" {comment}"
    return line + "\n"


def _fake_ed25519_private_key() -> str:
    raw = _random_bytes(250)
    b64 = base64.b64encode(raw).decode()
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN OPENSSH PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END OPENSSH PRIVATE KEY-----\n"


def _fake_ed25519_public_key(comment: str = "") -> str:
    raw = _random_bytes(32)
    key_type = b"ssh-ed25519"

    def _pack(data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + data

    blob = _pack(key_type) + _pack(raw)
    b64 = base64.b64encode(blob).decode()
    line = f"ssh-ed25519 {b64}"
    if comment:
        line += f" {comment}"
    return line + "\n"


def _fake_ecdsa_private_key() -> str:
    raw = _random_bytes(300)
    b64 = base64.b64encode(raw).decode()
    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    return "-----BEGIN OPENSSH PRIVATE KEY-----\n" + "\n".join(lines) + "\n-----END OPENSSH PRIVATE KEY-----\n"


def _fake_ecdsa_public_key(bits: int = 256, comment: str = "") -> str:
    curve = {256: "nistp256", 384: "nistp384", 521: "nistp521"}.get(bits, "nistp256")
    key_type = f"ecdsa-sha2-{curve}".encode()
    raw = _random_bytes(65 if bits <= 256 else 97 if bits <= 384 else 133)

    def _pack(data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + data

    blob = _pack(key_type) + _pack(curve.encode()) + _pack(raw)
    b64 = base64.b64encode(blob).decode()
    line = f"ecdsa-sha2-{curve} {b64}"
    if comment:
        line += f" {comment}"
    return line + "\n"


class Command_ssh_keygen(HoneyPotCommand):

    download_path = CowrieConfig.get("honeypot", "download_path", fallback=".")

    def start(self) -> None:
        try:
            optlist, args = getopt.getopt(
                self.args, "t:b:f:N:C:qvhylABHRDeEGJKMOPQSTUVWXYZ",
                ["help"]
            )
        except getopt.GetoptError as e:
            self.errorWrite(f"ssh-keygen: {e}\n")
            self.exit()
            return

        key_type = "rsa"
        bits = 0  # 0 = default for type
        output_file = ""
        passphrase = None
        comment = ""
        quiet = False

        for o, a in optlist:
            if o == "-t":
                key_type = a.lower()
            elif o == "-b":
                try:
                    bits = int(a)
                except ValueError:
                    self.errorWrite(f"ssh-keygen: invalid number: {a}\n")
                    self.exit()
                    return
            elif o == "-f":
                output_file = a
            elif o == "-N":
                passphrase = a
            elif o == "-C":
                comment = a
            elif o == "-q":
                quiet = True
            elif o in ("-h", "--help"):
                self._usage()
                return
            elif o == "-l":
                self._fingerprint(args)
                return
            elif o == "-y":
                self._read_public(args)
                return

        if key_type not in ("rsa", "ed25519", "ecdsa", "dsa"):
            self.errorWrite(f"ssh-keygen: unknown key type {key_type}\n")
            self.exit()
            return

        # Default bits per type
        if bits == 0:
            bits = {"rsa": 2048, "ed25519": 256, "ecdsa": 256, "dsa": 1024}[key_type]

        # Default output file
        if not output_file:
            home = getattr(self.protocol.user.avatar, "home", "/root")
            output_file = f"{home}/.ssh/id_{key_type}"

        # Resolve path
        priv_path = self.fs.resolve_path(output_file, self.protocol.cwd)
        pub_path = priv_path + ".pub"

        # Check if file exists — with -q, silently overwrite
        if self.fs.exists(priv_path) and not quiet:
            # In non-quiet mode, real ssh-keygen would prompt.
            # We auto-confirm since we can't do interactive prompts reliably.
            if not quiet:
                self.write(f"{priv_path} already exists.\nOverwriting.\n")

        # Ensure parent directory exists
        parent_dir = os.path.dirname(priv_path)
        if not self.fs.exists(parent_dir):
            try:
                self.fs.mkdir(
                    parent_dir,
                    self.protocol.user.uid,
                    self.protocol.user.gid,
                    4096,
                    0o700,
                )
            except OSError:
                self.errorWrite(
                    f"ssh-keygen: {os.path.dirname(output_file)}: No such file or directory\n"
                )
                self.exit()
                return

        # Generate key content
        if not comment:
            username = getattr(self.protocol.user, "username", "root")
            if isinstance(username, bytes):
                username = username.decode("utf-8", errors="replace")
            hostname = getattr(self.protocol.server, "hostname", "localhost")
            comment = f"{username}@{hostname}"

        if key_type == "rsa" or key_type == "dsa":
            priv_content = _fake_rsa_private_key(bits)
            pub_content = _fake_rsa_public_key(bits, comment)
            key_label = f"SHA256:{base64.b64encode(_random_bytes(32)).decode()[:43]}"
        elif key_type == "ed25519":
            priv_content = _fake_ed25519_private_key()
            pub_content = _fake_ed25519_public_key(comment)
            key_label = f"SHA256:{base64.b64encode(_random_bytes(32)).decode()[:43]}"
        elif key_type == "ecdsa":
            priv_content = _fake_ecdsa_private_key()
            pub_content = _fake_ecdsa_public_key(bits, comment)
            key_label = f"SHA256:{base64.b64encode(_random_bytes(32)).decode()[:43]}"
        else:
            priv_content = _fake_rsa_private_key(bits)
            pub_content = _fake_rsa_public_key(bits, comment)
            key_label = f"SHA256:{base64.b64encode(_random_bytes(32)).decode()[:43]}"

        # Write private key to virtual FS with real backing file
        self._create_file(priv_path, priv_content.encode(), 0o600)

        # Write public key
        self._create_file(pub_path, pub_content.encode(), 0o644)

        if not quiet:
            self.write(f"Generating public/private {key_type} key pair.\n")
            self.write(f"Your identification has been saved in {output_file}\n")
            self.write(f"Your public key has been saved in {output_file}.pub\n")
            self.write(f"The key fingerprint is:\n")
            self.write(f"{key_label} {comment}\n")
            self.write(f"The key's randomart image is:\n")
            self._write_randomart(key_type, bits)

        self.exit()

    def _create_file(self, virt_path: str, content: bytes, mode: int) -> None:
        """Create a file in the virtual FS backed by a real file on disk."""
        # Create virtual FS entry
        try:
            self.fs.mkfile(
                virt_path,
                self.protocol.user.uid,
                self.protocol.user.gid,
                len(content),
                mode,
            )
        except Exception as e:
            log.msg(f"ssh-keygen: failed to create {virt_path}: {e}")
            return

        # Write real backing file
        tmp_fname = "sshkeygen_{}_{}".format(
            time.strftime("%Y%m%d%H%M%S"),
            os.path.basename(virt_path),
        )
        safe_path = os.path.join(self.download_path, tmp_fname)

        try:
            with open(safe_path, "wb") as f:
                f.write(content)
            # Link virtual FS entry to real file
            fobj = self.fs.getfile(virt_path)
            if fobj:
                self.fs.update_realfile(fobj, safe_path)
        except Exception as e:
            log.msg(f"ssh-keygen: failed to write backing file {safe_path}: {e}")

    def _write_randomart(self, key_type: str, bits: int) -> None:
        """Generate a fake randomart image."""
        type_label = {"rsa": "RSA", "ed25519": "ED25519", "ecdsa": "ECDSA", "dsa": "DSA"}.get(key_type, "RSA")
        header = f"[{type_label} {bits}]"
        # Pad header to fit in 17-char box
        pad = 17 - len(header)
        left = pad // 2
        right = pad - left
        self.write(f"+{'-' * left}{header}{'-' * right}+\n")

        chars = " .o+=*BOX@%&#/^SE"
        for _row in range(9):
            line = ""
            for _col in range(17):
                line += random.choice(chars[:10])  # bias toward sparser chars
            self.write(f"|{line}|\n")

        footer = f"[{type_label}]"
        pad = 17 - len(footer)
        left = pad // 2
        right = pad - left
        self.write(f"+{'-' * left}{footer}{'-' * right}+\n")

    def _fingerprint(self, args: list[str]) -> None:
        """Handle ssh-keygen -l [-f file]."""
        filepath = ""
        if args:
            filepath = args[0]
        else:
            home = getattr(self.protocol.user.avatar, "home", "/root")
            filepath = f"{home}/.ssh/id_rsa.pub"

        resolved = self.fs.resolve_path(filepath, self.protocol.cwd)
        if not self.fs.exists(resolved):
            self.errorWrite(f"{filepath}: No such file or directory\n")
            self.exit()
            return

        fp = base64.b64encode(_random_bytes(32)).decode()[:43]
        self.write(f"2048 SHA256:{fp} no comment (RSA)\n")
        self.exit()

    def _read_public(self, args: list[str]) -> None:
        """Handle ssh-keygen -y [-f file] — read private key, output public."""
        filepath = ""
        if args:
            filepath = args[0]
        else:
            home = getattr(self.protocol.user.avatar, "home", "/root")
            filepath = f"{home}/.ssh/id_rsa"

        resolved = self.fs.resolve_path(filepath, self.protocol.cwd)
        if not self.fs.exists(resolved):
            self.errorWrite(f"{filepath}: No such file or directory\n")
            self.exit()
            return

        pub = _fake_rsa_public_key(2048, "")
        self.write(pub)
        self.exit()

    def _usage(self) -> None:
        self.write(
            """usage: ssh-keygen [-q] [-b bits] [-C comment] [-f output_keyfile] [-m format]
                 [-t dsa | ecdsa | ecdsa-sk | ed25519 | ed25519-sk | rsa]
                 [-N new_passphrase] [-O option] [-w provider]
       ssh-keygen -p [-f keyfile] [-m format] [-N new_passphrase]
                  [-P old_passphrase]
       ssh-keygen -i [-f input_keyfile] [-m key_format]
       ssh-keygen -e [-f input_keyfile] [-m key_format]
       ssh-keygen -y [-f input_keyfile]
       ssh-keygen -c [-C comment] [-f keyfile] [-P passphrase]
       ssh-keygen -l [-v] [-E fingerprint_hash] [-f input_keyfile]
       ssh-keygen -B [-f input_keyfile]
"""
        )
        self.exit()


commands["/usr/bin/ssh-keygen"] = Command_ssh_keygen
commands["ssh-keygen"] = Command_ssh_keygen
