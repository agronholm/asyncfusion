from __future__ import annotations

import sys
from socket import AF_INET, SOCK_STREAM, AddressFamily, SocketKind
from socket import fromfd as stdlib_fromfd
from socket import socket as stdlib_socket
from socket import socketpair as stdlib_socketpair

from asyncfusion import AsyncSocket

from .abc import HostnameResolver, SocketFactory


def socket(
    family: AddressFamily = AF_INET,
    type: SocketKind = SOCK_STREAM,
    proto: int = 0,
    fileno: int | None = None,
) -> SocketType:
    sock = stdlib_socket(family, type, proto, fileno)
    return _SocketType(sock)


def socketpair(
    family: AddressFamily, type: SocketKind = SOCK_STREAM, proto: int = 0
) -> tuple[SocketType, SocketType]:
    sock1, sock2 = stdlib_socketpair(family, type, proto)
    return _SocketType(sock1), _SocketType(sock2)


def fromfd(
    fd: int, family: AddressFamily, type: SocketKind, proto: int = 0
) -> SocketType:
    sock = stdlib_fromfd(fd, family, type, proto)
    return _SocketType(sock)


if sys.platform == "win32":

    def fromshare(data: bytes) -> SocketType:
        from socket import fromshare

        sock = fromshare(data)
        return _SocketType(sock)


def from_stdlib_socket(sock: socket) -> SocketType:
    return _SocketType(sock)


async def getaddrinfo(
    host: bytes | str | None,
    port: bytes | str | int | None,
    family: int = 0,
    type: int = 0,
    proto: int = 0,
    flags: int = 0,
) -> list[
    tuple[
        AddressFamily, SocketKind, int, str, tuple[str, int] | tuple[str, int, int, int]
    ]
]:
    raise NotImplementedError


async def getnameinfo(
    sockaddr: tuple[str, int] | tuple[str, int, int, int], flags: int
) -> tuple[str, str]:
    raise NotImplementedError


async def getprotobyname(name: str) -> int:
    raise NotImplementedError


def set_custom_hostname_resolver(
    hostname_resolver: HostnameResolver | None,
) -> HostnameResolver | None:
    raise NotImplementedError


def set_custom_socket_factory(
    socket_factory: SocketFactory | None,
) -> SocketFactory | None:
    raise NotImplementedError


class SocketType(AsyncSocket):
    __slots__ = ()

    def __init__(self) -> None:
        if type(self) is SocketType:
            raise TypeError(
                "SocketType is an abstract class; use trio.socket.socket if you "
                "want to construct a socket object"
            )


class _SocketType(AsyncSocket, SocketType):
    __slots__ = ()
