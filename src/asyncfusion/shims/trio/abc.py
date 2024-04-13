from __future__ import annotations

import sys
from abc import ABCMeta, abstractmethod
from socket import AF_INET, SOCK_STREAM, AddressFamily, SocketKind
from typing import TYPE_CHECKING, Generic, TypeVar

if sys.version_info >= (3, 12):
    from typing import Buffer
else:
    from typing_extensions import Buffer

if TYPE_CHECKING:
    from .socket import SocketType

T = TypeVar("T")
T_resource = TypeVar("T_resource")
SendType = TypeVar("SendType")
ReceiveType = TypeVar("ReceiveType")


class AsyncResource(metaclass=ABCMeta):
    @abstractmethod
    async def aclose(self) -> None: ...


class SendStream(AsyncResource):
    @abstractmethod
    async def send_all(self, data: Buffer) -> None: ...

    @abstractmethod
    async def wait_send_all_might_not_block(self) -> None: ...


class ReceiveStream(AsyncResource):
    @abstractmethod
    async def receive_some(self, max_bytes: int | None = None) -> bytes | bytearray: ...


class Stream(SendStream, ReceiveStream):
    pass


class HalfCloseableStream(Stream):
    @abstractmethod
    async def send_eof(self) -> None: ...


class Listener(AsyncResource, Generic[T_resource]):
    @abstractmethod
    async def accept(self) -> T_resource: ...


class SendChannel(AsyncResource, Generic[SendType]):
    async def send(self, value: SendType) -> None:
        pass


class ReceiveChannel(AsyncResource, Generic[ReceiveType]):
    async def receive(self) -> ReceiveType:
        pass


class Channel(SendChannel[T], ReceiveChannel[T]):
    pass


class HostnameResolver(metaclass=ABCMeta):
    @abstractmethod
    async def getaddrinfo(
        self,
        host: bytes | None,
        port: bytes | str | int | None,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[
        tuple[
            AddressFamily,
            SocketKind,
            int,
            str,
            tuple[str, int] | tuple[str, int, int, int],
        ]
    ]: ...


class SocketFactory(metaclass=ABCMeta):
    @abstractmethod
    def socket(
        self,
        family: AddressFamily = AF_INET,
        type: SocketKind = SOCK_STREAM,
        proto: int = 0,
    ) -> SocketType: ...
