from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from typing import Any

from asyncfusion.shims.asyncio import AbstractEventLoop

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

_ClientConnectedCallback: TypeAlias = Callable[["StreamReader", "StreamWriter"], "Awaitable[None] | None"]


async def open_connection(
    host: str | None = None,
    port: int | str | None = None,
    *,
    loop: AbstractEventLoop | None = None,
    limit: int = 65536,
    ssl_handshake_timeout: float | None = None,
) -> tuple[StreamReader, StreamWriter]:
    raise NotImplementedError


async def start_server(
    client_connected_cb: _ClientConnectedCallback,
    host: str | None = None,
    port: int | str | None = None,
    *,
    loop: AbstractEventLoop | None = None,
    limit: int = 65536,
    ssl_handshake_timeout: float | None = ...,
    **kwds: Any,
) -> Server:
    raise NotImplementedError


async def open_unix_connection(
    path: StrPath | None = None, *, limit: int = 65536, ssl=None, sock=None, server_hostname=None, ssl_handshake_timeout: float | None = None, ssl_shutdown_timeout: float | None = None
) -> tuple[StreamReader, StreamWriter]:
    raise NotImplementedError


async def start_unix_server(client_connected_cb, path=None, *, limit=None, sock=None, backlog: int = 100, ssl=None, ssl_handshake_timeout=None, ssl_shutdown_timeout=None, start_serving=True):
    raise NotImplementedError


class StreamWriter:
    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def writelines(self, data: bytes) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def can_write_eof(self) -> bool:
        raise NotImplementedError

    def write_eof(self) -> None:
        raise NotImplementedError

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        raise NotImplementedError

    async def drain(self) -> None:
        raise NotImplementedError

    async def start_tls(self, sslcontext, *, server_hostname=None, ssl_handshake_timeout=None, ssl_shutdown_timeout=None) -> None:
        raise NotImplementedError

    def is_closing(self) -> bool:
        raise NotImplementedError

    async def wait_closed(self) -> None:
        raise NotImplementedError


class StreamReader:
    def feed_eof(self) -> None:
        raise NotImplementedError

    async def read(self, n: int = -1) -> bytes:
        raise NotImplementedError

    async def readline(self) -> bytes:
        raise NotImplementedError

    async def readexactly(self, n: int) -> bytes:
        raise NotImplementedError

    async def readuntil(self, separator: bytes = b"\n") -> bytes:
        raise NotImplementedError

    def at_eof(self) -> bool:
        raise NotImplementedError
