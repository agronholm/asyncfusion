from __future__ import annotations

import sys
from collections.abc import Awaitable, Callable
from os import PathLike
from ssl import SSLContext
from typing import Generic, TypeVar

from submodules.trio.src.trio import CancelScope

from ._tasks import TASK_STATUS_IGNORED, Nursery, TaskStatus
from .abc import AsyncResource, HalfCloseableStream, ReceiveStream, SendStream

if sys.version_info >= (3, 12):
    from typing import Buffer
else:
    from typing_extensions import Buffer

T_Stream = TypeVar("T_Stream")
T_Listener = TypeVar("T_Listener")
SendStreamT = TypeVar("SendStreamT", bound=SendStream)
ReceiveStreamT = TypeVar("ReceiveStreamT", bound=ReceiveStream)


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


async def aclose_forcefully(resource: AsyncResource) -> None:
    with CancelScope() as cs:
        cs.cancel()
        await resource.aclose()


class StapledStream(HalfCloseableStream, Generic[SendStreamT, ReceiveStreamT]):
    def __init__(self, send_stream: SendStreamT, receive_stream: ReceiveStreamT):
        self.send_stream = send_stream
        self.receive_stream = receive_stream

    async def send_all(self, data: Buffer) -> None:
        return await self.send_stream.send_all(data)

    async def wait_send_all_might_not_block(self) -> None:
        return await self.send_stream.wait_send_all_might_not_block()

    async def send_eof(self) -> None:
        if isinstance(self.send_stream, HalfCloseableStream):
            await self.send_stream.send_eof()
        else:
            await self.send_stream.aclose()

    async def receive_some(self, max_bytes: int | None = None) -> bytes:
        return await self.receive_stream.receive_some(max_bytes)

    async def aclose(self) -> None:
        try:
            await self.send_stream.aclose()
        finally:
            await self.receive_stream.aclose()
