from __future__ import annotations

from collections.abc import Iterable
from socket import socket

from .events import AbstractEventLoop, AbstractServer


class Server(AbstractServer):
    def __init__(
        self,
        loop: AbstractEventLoop,
        sockets: Iterable[socket],
        protocol_factory: _ProtocolFactory,
        ssl_context: _SSLContext,
        backlog: int,
        ssl_handshake_timeout: float | None,
        ssl_shutdown_timeout: float | None = None,
    ) -> None:
        self._loop = loop
        self._sockets = tuple(sockets)

    def get_loop(self) -> AbstractEventLoop:
        return self._loop

    def is_serving(self) -> bool:
        raise NotImplementedError

    async def start_serving(self) -> None:
        raise NotImplementedError

    async def serve_forever(self) -> None:
        raise NotImplementedError

    @property
    def sockets(self) -> tuple[socket, ...]:
        return self._sockets

    def close(self) -> None:
        raise NotImplementedError

    async def wait_closed(self) -> None:
        raise NotImplementedError
