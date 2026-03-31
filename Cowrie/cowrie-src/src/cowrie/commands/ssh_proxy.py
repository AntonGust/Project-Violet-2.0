"""Interactive SSH proxy for HoneyNet mode.

When HONEYNET_MODE=true, the ssh command proxies real SSH connections
to neighbor Cowrie containers instead of simulating a login. This module
uses paramiko in a background thread to maintain a real SSH session while
relaying I/O through Cowrie's terminal layer via the Twisted reactor.
"""

from __future__ import annotations

import os
import socket
import threading
import time

import paramiko
from twisted.internet import reactor
from twisted.python import log


class SSHProxySession:
    """Manages a real SSH connection to a neighbor Cowrie container."""

    def __init__(self, host: str, port: int, username: str, password: str, command):
        """
        Args:
            host: Target IP address
            port: Target SSH port (typically 2222)
            username: SSH username
            password: SSH password
            command: The Command_ssh instance that owns this proxy
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.command = command
        self.active = False

        self._client: paramiko.SSHClient | None = None
        self._channel: paramiko.Channel | None = None
        self._reader_thread: threading.Thread | None = None

    # Return codes from connect()
    CONNECT_OK = "ok"
    CONNECT_AUTH_FAILED = "auth_failed"
    CONNECT_UNREACHABLE = "unreachable"

    def connect(self) -> str:
        """Open real SSH, authenticate, request shell, start I/O relay.

        Returns:
            CONNECT_OK on success,
            CONNECT_AUTH_FAILED on bad credentials,
            CONNECT_UNREACHABLE on network/connection errors.
        """
        try:
            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
        except paramiko.AuthenticationException:
            reactor.callFromThread(  # type: ignore[attr-defined]
                self.command.write, "Permission denied, please try again.\n"
            )
            self._cleanup()
            return self.CONNECT_AUTH_FAILED
        except socket.timeout:
            log.msg(f"SSH proxy connection timed out: {self.host}:{self.port}")
            self._cleanup()
            return self.CONNECT_UNREACHABLE
        except ConnectionRefusedError:
            log.msg(f"SSH proxy connection refused: {self.host}:{self.port}")
            self._cleanup()
            return self.CONNECT_UNREACHABLE
        except Exception as e:
            log.msg(f"SSH proxy connection failed: {e}")
            self._cleanup()
            return self.CONNECT_UNREACHABLE

        for attempt in range(2):
            try:
                self._channel = self._client.invoke_shell(
                    term="xterm",
                    width=80,
                    height=24,
                )
                self._channel.settimeout(0.1)
                break
            except Exception as e:
                if attempt == 0 and "Channel closed" in str(e):
                    log.msg(
                        f"SSH proxy shell failed on first attempt (filesystem init race), retrying: {e}"
                    )
                    self._cleanup()
                    time.sleep(0.5)
                    # Re-establish connection for retry
                    try:
                        self._client = paramiko.SSHClient()
                        self._client.set_missing_host_key_policy(
                            paramiko.AutoAddPolicy()
                        )
                        self._client.connect(
                            hostname=self.host,
                            port=self.port,
                            username=self.username,
                            password=self.password,
                            timeout=10,
                            look_for_keys=False,
                            allow_agent=False,
                        )
                    except Exception:
                        self._cleanup()
                        return self.CONNECT_UNREACHABLE
                    continue
                reactor.callFromThread(  # type: ignore[attr-defined]
                    self.command.write, f"ssh: failed to open shell: {e}\n"
                )
                log.msg(f"SSH proxy shell request failed: {e}")
                self._cleanup()
                return self.CONNECT_UNREACHABLE

        self.active = True

        # Start background reader thread
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            daemon=True,
            name=f"ssh-proxy-{self.host}",
        )
        self._reader_thread.start()

        log.msg(f"SSH proxy connected to {self.host}:{self.port} as {self.username}")
        return self.CONNECT_OK

    def relay_input(self, data: str) -> None:
        """Forward attacker keystrokes to the remote shell."""
        if not self.active or not self._channel:
            return
        try:
            self._channel.send(data + "\n")
        except Exception:
            self.disconnect()

    def relay_input_bytes(self, data: bytes) -> None:
        """Forward raw bytes to the remote shell (for special keys)."""
        if not self.active or not self._channel:
            return
        try:
            self._channel.send(data)
        except Exception:
            self.disconnect()

    def disconnect(self) -> None:
        """Tear down the proxy connection and return control to local shell."""
        if not self.active:
            return
        self.active = False
        self._cleanup()
        # Schedule exit on the reactor thread
        reactor.callFromThread(self._on_disconnect)  # type: ignore[attr-defined]

    def _on_disconnect(self) -> None:
        """Called on reactor thread when proxy disconnects."""
        self.command.write("Connection to {} closed.\n".format(self.host))
        # Restore the original hostname and cwd
        if hasattr(self.command, '_saved_hostname'):
            self.command.protocol.hostname = self.command._saved_hostname
        if hasattr(self.command, '_saved_cwd'):
            self.command.protocol.cwd = self.command._saved_cwd
        self.command.exit()

    def _read_loop(self) -> None:
        """Background thread: read from remote SSH and relay to attacker terminal."""
        while self.active and self._channel:
            try:
                data = self._channel.recv(4096)
                if not data:
                    # Remote closed
                    self.disconnect()
                    return
                # Send output to attacker's terminal via reactor thread
                reactor.callFromThread(  # type: ignore[attr-defined]
                    self.command.writeBytes, data
                )
            except socket.timeout:
                # Timeout on non-blocking recv — just keep looping
                continue
            except paramiko.ssh_exception.SSHException:
                self.disconnect()
                return
            except OSError:
                # Socket closed
                self.disconnect()
                return

    def _cleanup(self) -> None:
        """Close SSH resources."""
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
