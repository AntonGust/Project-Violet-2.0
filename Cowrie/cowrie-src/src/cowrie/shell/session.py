# Copyright (c) 2009-2014 Upi Tamminen <desaster@gmail.com>
# See the COPYRIGHT file for more information

from __future__ import annotations

from zope.interface import implementer

from twisted.conch.interfaces import ISession
from twisted.conch.ssh import session
from twisted.python import log

from cowrie.core.config import CowrieConfig
from cowrie.insults import insults
from cowrie.shell import protocol


@implementer(ISession)
class SSHSessionForCowrieUser:
    def __init__(self, avatar, reactor=None):
        """
        Construct an C{SSHSessionForCowrieUser}.

        @param avatar: The L{CowrieUser} for whom this is an SSH session.
        @param reactor: An L{IReactorProcess} used to handle shell and exec
            requests. Uses the default reactor if None.
        """
        self.protocol = None
        self.avatar = avatar
        self.server = avatar.server
        self.uid = avatar.uid
        self.gid = avatar.gid
        self.username = avatar.username
        hostname = CowrieConfig.get("honeypot", "hostname", fallback="localhost")
        self.environ = {
            "HOME": self.avatar.home,
            "HOSTNAME": hostname,
            "LANG": "en_US.UTF-8",
            "LANGUAGE": "en_US:en",
            "LOGNAME": self.username,
            "MAIL": f"/var/mail/{self.username}",
            "PWD": self.avatar.home,
            "SHELL": "/bin/bash",
            "SHLVL": "1",
            "TMOUT": "1800",
            "UID": str(self.uid),
            "USER": self.username,
        }
        if self.uid == 0:
            self.environ["PATH"] = (
                "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            )
        else:
            self.environ["PATH"] = (
                "/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games"
            )

        try:
            self.server.initFileSystem(self.avatar.home)
        except Exception as e:
            log.msg(f"initFileSystem failed for {self.avatar.home}: {e}")
            raise

        if self.avatar.temporary:
            self.server.fs.mkdir(self.avatar.home, self.uid, self.gid, 4096, 755)

    def openShell(self, processprotocol):
        self.protocol = insults.LoggingServerProtocol(
            protocol.HoneyPotInteractiveProtocol, self
        )
        self.protocol.makeConnection(processprotocol)
        processprotocol.makeConnection(session.wrapProtocol(self.protocol))

    def getPty(self, terminal, windowSize, attrs):
        self.environ["TERM"] = terminal.decode("utf-8")
        log.msg(
            eventid="cowrie.client.size",
            width=windowSize[1],
            height=windowSize[0],
            format="Terminal Size: %(width)s %(height)s",
        )
        self.windowSize = windowSize

    def execCommand(self, processprotocol, cmd):
        self.protocol = insults.LoggingServerProtocol(
            protocol.HoneyPotExecProtocol, self, cmd
        )
        self.protocol.makeConnection(processprotocol)
        processprotocol.makeConnection(session.wrapProtocol(self.protocol))

    def closed(self) -> None:
        """
        this is reliably called on both logout and disconnect
        we notify the protocol here we lost the connection
        """
        if self.protocol:
            self.protocol.connectionLost("disconnected")
            self.protocol = None

    def eofReceived(self) -> None:
        if self.protocol:
            self.protocol.eofReceived()

    def windowChanged(self, windowSize):
        self.windowSize = windowSize
