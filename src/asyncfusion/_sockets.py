from __future__ import annotations

import socket
from functools import singledispatch
from socket import AddressFamily, SocketKind
from types import TracebackType
from typing import Optional, overload
import sys

from ._eventloop import current_event_loop

if sys.version_info >= (3, 12):
    from collections.abc import Buffer
else:
    from typing_extensions import Buffer

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

IPAddress: TypeAlias = "tuple[str, int] | tuple[str, int, int, int]"
SocketAddress: TypeAlias = "str | IPAddress"


# def socket(family: AddressFamily = AddressFamily.AF_INET, type: SocketKind = SocketKind.SOCK_STREAM, proto: int = 0, fileno: int | None = None) -> AsyncSocket:
#     sock = socket.socket(family, type, proto, fileno)
#     return AsyncSocket(sock)

class AsyncSocket:
    __slots__ = ("_loop", "_sock", "_fileno")

    @singledispatch
    def __init__(self, sock: socket.socket):
        self._loop = current_event_loop()
        self._sock = sock
        self._sock.setblocking(False)
        self._fileno = sock.fileno()

    @__init__.register
    def __init__(self, family: AddressFamily = AddressFamily.AF_INET, type: SocketKind = SocketKind.SOCK_STREAM, proto: int = 0, fileno: Optional[int] = None):
        self._loop = current_event_loop()
        self._sock = socket.socket(family, type, proto, fileno)
        self._sock.setblocking(False)
        self._fileno = self._sock.fileno()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._loop.sock_close(self._fileno)
        self._sock.detach()
        del self._fileno
        del self._loop

    @property
    def family(self) -> AddressFamily:
        return self._sock.family

    @property
    def type(self) -> SocketKind:
        return self._sock.type

    @property
    def proto(self) -> int:
        return self._sock.proto

    def fileno(self) -> int:
        return self._fileno

    async def accept(self) -> tuple[AsyncSocket, SocketAddress]:
        fileno, addr = await self._loop.sock_accept(self._fileno)
        sock = AsyncSocket(self._sock.family, socket.SOCK_STREAM, 0, fileno)
        return sock, addr

    async def bind(self, address: SocketAddress, /) -> None:
        # TODO: make this use threads or something
        self._sock.bind(address)

    async def connect(self, address: SocketAddress, /) -> None:
        if isinstance(address, tuple) and isinstance(address[0], str):
            address = (address[0].encode("ascii"), address[1])

        return await self._loop.sock_connect(self._fileno, self._sock.family, address)

    def listen(self, backlog: int = 5, /) -> None:
        self._sock.listen(backlog)

    async def recv(self, max_bytes: int, /) -> bytes:
        return await self._loop.sock_recv(self._fileno, max_bytes)

    async def recvfrom(self, max_bytes: int, /) -> tuple[bytes, SocketAddress]:
        return await self._loop.sock_recvfrom(self._fileno, max_bytes)

    async def send(self, data: bytes, /) -> int:
        return await self._loop.sock_send(self._fileno, data)

    async def sendall(self, data: bytes, /) -> None:
        view = memoryview(data)
        while view:
            bytes_sent = await self._loop.sock_send(self._fileno, data)
            view = view[bytes_sent:]

    async def sendto(self, data: bytes, address: SocketAddress, /) -> int:
        return await self._loop.sock_sendto(self._fileno, data, address)

    @overload
    def setsockopt(self, level: int, optname: int, value: int | Buffer, /) -> None:
        ...

    @overload
    def setsockopt(self, level: int, optname: int, value: None, optlen: int, /) -> None:
        ...

    def setsockopt(self, level, optname, value: int | Buffer | None, *args) -> None:
        self._sock.setsockopt(level, optname, value, *args)

    def share(self, process_id: int, /) -> bytes:
        return self._sock.share(process_id)

    def shutdown(self, how: int, /) -> None:
        self._sock.shutdown(how)


# async def connect_tcp(host: str | bytes, port: int) -> AsyncSocket:
#     host_bytes = host.encode("ascii") if isinstance(host, str) else host
#     loop = current_event_loop()
#     sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     fd = sock.fileno()
#     try:
#         await loop.sock_connect(fd, sock.family, (host_bytes, port))
#     except BaseException as exc:
#         print("Connect failed:", type(exc).__name__, exc)
#         await loop.sock_close(fd)
#         print("Closed fd")
#         raise
#
#     return AsyncSocket(loop, sock)
