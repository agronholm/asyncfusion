from __future__ import annotations

from collections.abc import Awaitable, Callable
from os import PathLike
from ssl import SSLContext
from typing import Generic, TypeVar

from ._tasks import TASK_STATUS_IGNORED, Nursery, TaskStatus

T_Stream = TypeVar("T_Stream")
T_Listener = TypeVar("T_Listener")


class SocketStream:
    pass


class SSLStream(Generic[T_Stream]):
    pass


class SocketListener:
    pass


class SSLListener(Generic[T_Listener]):
    pass


async def open_tcp_stream(
    host: str | bytes,
    port: int,
    *,
    happy_eyeballs_delay: float | None = 0.25,
    local_address: str | None = None,
) -> SocketStream:
    raise NotImplementedError


async def serve_tcp(
    handler: Callable[[SocketStream], Awaitable[object]],
    port: int,
    *,
    host: str | bytes | None = None,
    backlog: int | None = None,
    handler_nursery: Nursery | None = None,
    task_status: TaskStatus[list[SocketListener]] = TASK_STATUS_IGNORED,
) -> None:
    raise NotImplementedError


async def open_ssl_over_tcp_stream(
    host: str | bytes,
    port: int,
    *,
    https_compatible: bool = False,
    ssl_context: SSLContext | None = None,
    happy_eyeballs_delay: float | None = 0.25,
) -> SSLStream[SocketStream]:
    raise NotImplementedError


async def serve_ssl_over_tcp(
    handler: Callable[[SSLStream[SocketStream]], Awaitable[object]],
    port: int,
    ssl_context: SSLContext,
    *,
    host: str | bytes | None = None,
    https_compatible: bool = False,
    backlog: int | None = None,
    handler_nursery: Nursery | None = None,
    task_status: TaskStatus[list[SSLListener[SocketStream]]] = TASK_STATUS_IGNORED,
) -> None:
    raise NotImplementedError


async def open_unix_socket(
    filename: str | bytes | PathLike[str] | PathLike[bytes],
) -> SocketStream:
    raise NotImplementedError


async def open_tcp_listeners(
    port: int, *, host: str | bytes | None = None, backlog: int | None = None
) -> list[SocketListener]:
    raise NotImplementedError


async def open_ssl_over_tcp_listeners(
    port: int,
    ssl_context: SSLContext,
    *,
    host: str | bytes | None = None,
    https_compatible: bool = False,
    backlog: int | None = None,
) -> list[SSLListener[SocketStream]]:
    raise NotImplementedError
