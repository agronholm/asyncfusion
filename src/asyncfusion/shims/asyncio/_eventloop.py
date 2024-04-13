from __future__ import annotations

import sys
from collections.abc import Awaitable
from socket import socket
from typing import Any, TypeVar, Union

import asyncfusion

from .events import AbstractEventLoop
from .futures import Future

if sys.version_info >= (3, 12):
    from typing import Buffer
else:
    from typing_extensions import Buffer

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

_T = TypeVar("_T")
_Address: TypeAlias = Union[tuple[Any, ...], str, Buffer]


class AsyncFusionEventLoop(AbstractEventLoop):
    def __init__(self, event_loop: asyncfusion.EventLoop):
        self._event_loop = event_loop

    def time(self) -> float:
        return self._event_loop.time()

    async def sock_connect(self, sock: socket, address: _Address) -> None:
        await self._event_loop.sock_connect(sock, address)

    async def sock_accept(self, sock: socket) -> tuple[socket, Any]:
        return await self._event_loop.sock_accept(sock)

    async def sock_recv(self, sock: socket, nbytes: int) -> bytes:
        return await self._event_loop.sock_recv(sock, nbytes)

    async def sock_recvfrom(self, sock: socket, bufsize: int) -> tuple[bytes, Any]:
        return await self._event_loop.sock_recvfrom(sock, bufsize)

    def create_future(self) -> Future[Any]:
        return Future()

    def run_until_complete(self, future: Awaitable[_T]) -> _T:
        raise NotImplementedError

    def run_forever(self) -> None:
        self._event_loop.run_forever()
