from __future__ import annotations

import ssl
import sys
import threading
from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Coroutine, Sequence
from contextvars import Context
from functools import total_ordering
from socket import AddressFamily, SocketKind, socket
from types import TracebackType
from typing import IO, TYPE_CHECKING, Any, Literal, TypeVar, Union, overload

if sys.version_info >= (3, 11):
    from typing import Self, TypeVarTuple, Unpack
else:
    from typing_extensions import Self, TypeVarTuple, Unpack

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from .futures import Future
    from .tasks import Task

_T = TypeVar("_T")
_Ts = TypeVarTuple("_Ts")
_ProtocolT = TypeVar("_ProtocolT", bound=BaseProtocol)
_Context: TypeAlias = dict[str, Any]
_ExceptionHandler: TypeAlias = Callable[[AbstractEventLoop, _Context], object]
_ProtocolFactory: TypeAlias = Callable[[], BaseProtocol]
_SSLContext: TypeAlias = Union[bool, None, ssl.SSLContext]
TaskFactory: TypeAlias = Callable[
    ["AbstractEventLoop", Coroutine[Any, Any, _T]], Task[_T]
]


class _AsyncioLocal(threading.local):
    loop: AbstractEventLoop


_local = _AsyncioLocal()


class Handle:
    __slots__ = ("_callback", "_args", "_loop", "_context", "_cancelled")

    def __init__(
        self,
        callback: Callable[..., object],
        args: Sequence[Any],
        loop: AbstractEventLoop,
        context: Context | None = None,
    ) -> None:
        self._callback: Callable[..., object] | None = callback
        self._args: Sequence[Any] | None = args
        self._loop = loop
        self._context = context
        self._cancelled = False

    def cancel(self) -> None:
        if not self._cancelled:
            self._cancelled = True
            self._callback = None
            self._args = None

    def _run(self) -> None:
        self._callback(*self._args)

    def cancelled(self) -> bool:
        return self._cancelled

    def get_context(self) -> Context:
        return self._context


@total_ordering
class TimerHandle(Handle):
    def __init__(
        self,
        when: float,
        callback: Callable[..., object],
        args: Sequence[Any],
        loop: AbstractEventLoop,
        context: Context | None = None,
    ) -> None:
        super().__init__(callback, args, loop, context)
        self._when = when

    def __hash__(self) -> int:
        return hash(self._when)

    def when(self) -> float:
        return self._when

    def __lt__(self, other: object) -> bool:
        if isinstance(other, TimerHandle):
            return self.when() < other.when()

        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TimerHandle):
            return self.when() == other.when()

        return NotImplemented


class AbstractServer(metaclass=ABCMeta):
    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def get_loop(self) -> AbstractEventLoop:
        pass

    @abstractmethod
    def is_serving(self) -> bool:
        pass

    @abstractmethod
    async def start_serving(self) -> None:
        pass

    @abstractmethod
    async def serve_forever(self) -> None:
        pass

    @abstractmethod
    async def wait_closed(self) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
        await self.wait_closed()


class AbstractEventLoop(metaclass=ABCMeta):
    slow_callback_duration: float

    @abstractmethod
    def run_forever(self) -> None:
        pass

    @abstractmethod
    def run_until_complete(self, future: _AwaitableLike[_T]) -> _T:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def is_running(self) -> bool:
        pass

    @abstractmethod
    def is_closed(self) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    async def shutdown_asyncgens(self) -> None:
        pass

    @abstractmethod
    def call_soon(
        self,
        callback: Callable[[Unpack[_Ts]], object],
        *args: Unpack[_Ts],
        context: Context | None = None,
    ) -> Handle: ...

    @abstractmethod
    def call_later(
        self,
        delay: float,
        callback: Callable[[Unpack[_Ts]], object],
        *args: Unpack[_Ts],
        context: Context | None = None,
    ) -> TimerHandle: ...

    @abstractmethod
    def call_at(
        self,
        when: float,
        callback: Callable[[Unpack[_Ts]], object],
        *args: Unpack[_Ts],
        context: Context | None = None,
    ) -> TimerHandle: ...

    @abstractmethod
    def time(self) -> float:
        pass

    @abstractmethod
    def create_future(self) -> Future[Any]:
        pass

    @abstractmethod
    def create_task(
        self,
        coro: _CoroutineLike[_T],
        *,
        name: str | None = None,
        context: Context | None = None,
    ) -> Task[_T]:
        pass

    @abstractmethod
    def set_task_factory(self, factory: _TaskFactory | None) -> None:
        pass

    @abstractmethod
    def get_task_factory(self) -> _TaskFactory | None:
        pass

    @abstractmethod
    def call_soon_threadsafe(
        self,
        callback: Callable[[Unpack[_Ts]], object],
        *args: Unpack[_Ts],
        context: Context | None = None,
    ) -> Handle: ...

    @abstractmethod
    def run_in_executor(
        self, executor: Any, func: Callable[[Unpack[_Ts]], _T], *args: Unpack[_Ts]
    ) -> Future[_T]:
        pass

    @abstractmethod
    def set_default_executor(self, executor: Any) -> None:
        pass

    @abstractmethod
    async def getaddrinfo(
        self,
        host: bytes | str | None,
        port: bytes | str | int | None,
        *,
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
    ]:
        pass

    @abstractmethod
    async def getnameinfo(
        self, sockaddr: tuple[str, int] | tuple[str, int, int, int], flags: int = 0
    ) -> tuple[str, str]:
        pass

    @overload
    @abstractmethod
    async def create_connection(
        self,
        protocol_factory: Callable[[], _ProtocolT],
        host: str = ...,
        port: int = ...,
        *,
        ssl: _SSLContext = None,
        family: int = 0,
        proto: int = 0,
        flags: int = 0,
        sock: None = None,
        local_addr: tuple[str, int] | None = None,
        server_hostname: str | None = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
        happy_eyeballs_delay: float | None = None,
        interleave: int | None = None,
    ) -> tuple[Transport, _ProtocolT]: ...

    @overload
    @abstractmethod
    async def create_connection(
        self,
        protocol_factory: Callable[[], _ProtocolT],
        host: None = None,
        port: None = None,
        *,
        ssl: _SSLContext = None,
        family: int = 0,
        proto: int = 0,
        flags: int = 0,
        sock: socket,
        local_addr: None = None,
        server_hostname: str | None = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
        happy_eyeballs_delay: float | None = None,
        interleave: int | None = None,
    ) -> tuple[Transport, _ProtocolT]: ...

    @overload
    @abstractmethod
    async def create_server(
        self,
        protocol_factory: _ProtocolFactory,
        host: str | Sequence[str] | None = None,
        port: int = ...,
        *,
        family: int = ...,
        flags: int = ...,
        sock: None = None,
        backlog: int = 100,
        ssl: _SSLContext = None,
        reuse_address: bool | None = None,
        reuse_port: bool | None = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
        start_serving: bool = True,
    ) -> Server: ...

    @overload
    @abstractmethod
    async def create_server(
        self,
        protocol_factory: _ProtocolFactory,
        host: None = None,
        port: None = None,
        *,
        family: int = ...,
        flags: int = ...,
        sock: socket = ...,
        backlog: int = 100,
        ssl: _SSLContext = None,
        reuse_address: bool | None = None,
        reuse_port: bool | None = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
        start_serving: bool = True,
    ) -> Server: ...

    @abstractmethod
    async def start_tls(
        self,
        transport: WriteTransport,
        protocol: BaseProtocol,
        sslcontext: ssl.SSLContext,
        *,
        server_side: bool = False,
        server_hostname: str | None = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
    ) -> Transport | None:
        pass

    async def create_unix_server(
        self,
        protocol_factory: _ProtocolFactory,
        path: StrPath | None = None,
        *,
        sock: socket | None = None,
        backlog: int = 100,
        ssl: _SSLContext = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
        start_serving: bool = True,
    ) -> Server:
        pass

    async def connect_accepted_socket(
        self,
        protocol_factory: Callable[[], _ProtocolT],
        sock: socket,
        *,
        ssl: _SSLContext = None,
        ssl_handshake_timeout: float | None = None,
        ssl_shutdown_timeout: float | None = None,
    ) -> tuple[Transport, _ProtocolT]:
        pass

    @abstractmethod
    async def sock_sendfile(
        self,
        sock: socket,
        file: IO[bytes],
        offset: int = 0,
        count: int | None = None,
        *,
        fallback: bool | None = None,
    ) -> int:
        pass

    @abstractmethod
    async def sendfile(
        self,
        transport: WriteTransport,
        file: IO[bytes],
        offset: int = 0,
        count: int | None = None,
        *,
        fallback: bool = True,
    ) -> int:
        pass

    @abstractmethod
    async def create_datagram_endpoint(
        self,
        protocol_factory: Callable[[], _ProtocolT],
        local_addr: tuple[str, int] | str | None = None,
        remote_addr: tuple[str, int] | str | None = None,
        *,
        family: int = 0,
        proto: int = 0,
        flags: int = 0,
        reuse_address: bool | None = None,
        reuse_port: bool | None = None,
        allow_broadcast: bool | None = None,
        sock: socket | None = None,
    ) -> tuple[DatagramTransport, _ProtocolT]:
        pass

    # Pipes and subprocesses.
    @abstractmethod
    async def connect_read_pipe(
        self, protocol_factory: Callable[[], _ProtocolT], pipe: Any
    ) -> tuple[ReadTransport, _ProtocolT]:
        pass

    @abstractmethod
    async def connect_write_pipe(
        self, protocol_factory: Callable[[], _ProtocolT], pipe: Any
    ) -> tuple[WriteTransport, _ProtocolT]:
        pass

    @abstractmethod
    async def subprocess_shell(
        self,
        protocol_factory: Callable[[], _ProtocolT],
        cmd: bytes | str,
        *,
        stdin: int | IO[Any] | None = -1,
        stdout: int | IO[Any] | None = -1,
        stderr: int | IO[Any] | None = -1,
        universal_newlines: Literal[False] = False,
        shell: Literal[True] = True,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        text: Literal[False] | None = ...,
        **kwargs: Any,
    ) -> tuple[SubprocessTransport, _ProtocolT]:
        pass

    @abstractmethod
    async def subprocess_exec(
        self,
        protocol_factory: Callable[[], _ProtocolT],
        program: Any,
        *args: Any,
        stdin: int | IO[Any] | None = -1,
        stdout: int | IO[Any] | None = -1,
        stderr: int | IO[Any] | None = -1,
        universal_newlines: Literal[False] = False,
        shell: Literal[False] = False,
        bufsize: Literal[0] = 0,
        encoding: None = None,
        errors: None = None,
        **kwargs: Any,
    ) -> tuple[SubprocessTransport, _ProtocolT]:
        pass

    @abstractmethod
    def add_reader(
        self,
        fd: FileDescriptorLike,
        callback: Callable[[Unpack[_Ts]], Any],
        *args: Unpack[_Ts],
    ) -> None:
        pass

    @abstractmethod
    def remove_reader(self, fd: FileDescriptorLike) -> bool:
        pass

    @abstractmethod
    def add_writer(
        self,
        fd: FileDescriptorLike,
        callback: Callable[[Unpack[_Ts]], Any],
        *args: Unpack[_Ts],
    ) -> None:
        pass

    @abstractmethod
    def remove_writer(self, fd: FileDescriptorLike) -> bool:
        pass

    @abstractmethod
    async def sock_recv(self, sock: socket, nbytes: int) -> bytes:
        pass

    @abstractmethod
    async def sock_recv_into(self, sock: socket, buf: WriteableBuffer) -> int:
        pass

    @abstractmethod
    async def sock_sendall(self, sock: socket, data: ReadableBuffer) -> None:
        pass

    @abstractmethod
    async def sock_connect(self, sock: socket, address: _Address) -> None:
        pass

    @abstractmethod
    async def sock_accept(self, sock: socket) -> tuple[socket, _RetAddress]:
        pass

    @abstractmethod
    async def sock_recvfrom(
        self, sock: socket, bufsize: int
    ) -> tuple[bytes, _RetAddress]:
        pass

    @abstractmethod
    async def sock_recvfrom_into(
        self, sock: socket, buf: WriteableBuffer, nbytes: int = 0
    ) -> tuple[int, _RetAddress]:
        pass

    @abstractmethod
    async def sock_sendto(
        self, sock: socket, data: ReadableBuffer, address: _Address
    ) -> int:
        pass

    @abstractmethod
    def add_signal_handler(
        self, sig: int, callback: Callable[[Unpack[_Ts]], object], *args: Unpack[_Ts]
    ) -> None:
        pass

    @abstractmethod
    def remove_signal_handler(self, sig: int) -> bool:
        pass

    # Error handlers.
    @abstractmethod
    def set_exception_handler(self, handler: _ExceptionHandler | None) -> None:
        pass

    @abstractmethod
    def get_exception_handler(self) -> _ExceptionHandler | None:
        pass

    @abstractmethod
    def default_exception_handler(self, context: _Context) -> None:
        pass

    @abstractmethod
    def call_exception_handler(self, context: _Context) -> None:
        pass

    # Debug flag management.
    @abstractmethod
    def get_debug(self) -> bool:
        pass

    @abstractmethod
    def set_debug(self, enabled: bool) -> None:
        pass

    @abstractmethod
    async def shutdown_default_executor(self) -> None:
        pass


def get_running_loop() -> AbstractEventLoop:
    try:
        return _local.loop
    except AttributeError:
        raise RuntimeError("no running event loop") from None


def get_event_loop() -> AbstractEventLoop:
    try:
        return get_running_loop()
    except RuntimeError:
        raise NotImplementedError(
            "using get_event_loop() to create a new event loop is not supported in "
            "AsyncFusion"
        ) from None


def set_event_loop(loop: AbstractEventLoop) -> None:
    if not isinstance(loop, AbstractEventLoop):
        raise TypeError("loop must be an instance of AbstractEventLoop")

    _local.loop = loop


def new_event_loop() -> None:
    raise NotImplementedError("this function is not supported in AsyncFusion")
