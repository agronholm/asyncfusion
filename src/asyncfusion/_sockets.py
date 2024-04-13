from __future__ import annotations

import socket
import sys
from socket import AddressFamily, SocketKind
from types import TracebackType
from typing import Any, Optional, overload

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


class AsyncSocket:
    __slots__ = ("_loop", "_sock", "_fileno")

    def __init__(
        self,
        family: AddressFamily = AddressFamily.AF_INET,
        type: SocketKind = SocketKind.SOCK_STREAM,
        proto: int = 0,
        fileno: Optional[int] = None,  # noqa: UP007
    ):
        self._loop = current_event_loop()
        self._sock = socket.socket(family, type, proto, fileno)
        self._sock.setblocking(False)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._loop.sock_close(self._sock)
        self._sock.detach()
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
        return self._sock.fileno()

    async def accept(self) -> tuple[AsyncSocket, SocketAddress]:
        stdlib_sock, addr = await self._loop.sock_accept(self._sock)
        fileno = stdlib_sock.fileno()
        stdlib_sock.detach()
        sock = AsyncSocket(
            stdlib_sock.family, stdlib_sock.type, stdlib_sock.proto, fileno
        )
        return sock, addr

    async def bind(self, address: SocketAddress, /) -> None:
        # TODO: make this use threads or something
        self._sock.bind(address)

    async def connect(self, address: SocketAddress, /) -> None:
        return await self._loop.sock_connect(self._sock, address)

    def listen(self, backlog: int = 5, /) -> None:
        self._sock.listen(backlog)

    async def recv(self, max_bytes: int, /) -> bytes:
        return await self._loop.sock_recv(self._sock, max_bytes)

    async def recv_into(self, buf: Buffer, /) -> bytes:
        return await self._loop.sock_recv_into(self._sock, buf)

    async def recvfrom(self, max_bytes: int, /) -> tuple[bytes, SocketAddress]:
        return await self._loop.sock_recvfrom(self._sock, max_bytes)

    async def recvfrom_into(
        self, buf: Buffer, max_bytes: int = 0, /
    ) -> tuple[int, SocketAddress]:
        return await self._loop.sock_recvfrom_into(self._sock, buf, max_bytes)

    async def send(self, data: bytes, /) -> int:
        return await self._loop.sock_send(self._sock, data)

    async def sendall(self, data: bytes, /) -> None:
        view = memoryview(data)
        while view:
            bytes_sent = await self._loop.sock_send(self._sock, data)
            view = view[bytes_sent:]

    async def sendto(self, data: bytes, address: SocketAddress, /) -> int:
        return await self._loop.sock_sendto(self._sock, data, address)

    @overload
    def setsockopt(self, level: int, optname: int, value: int | Buffer, /) -> None: ...

    @overload
    def setsockopt(
        self, level: int, optname: int, value: None, optlen: int, /
    ) -> None: ...

    def setsockopt(
        self, level: int, optname: int, value: int | Buffer | None, *args: Any
    ) -> None:
        self._sock.setsockopt(level, optname, value, *args)

    def share(self, process_id: int, /) -> bytes:
        return self._sock.share(process_id)

    def shutdown(self, how: int, /) -> None:
        self._sock.shutdown(how)
