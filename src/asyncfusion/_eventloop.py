from __future__ import annotations

import sys
import time
from collections.abc import Awaitable, Callable, Coroutine
from contextvars import ContextVar
from socket import socket
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, TypeVar

from ._futures import Future
from ._tasks import Task
from ._utils import infinite

if sys.version_info >= (3, 12):
    from typing import Buffer
else:
    from typing_extensions import Buffer

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

try:
    from sniffio import thread_local as sniffio_thread_local
except ImportError:
    sniffio_thread_local = SimpleNamespace(name=None)  # type: ignore[assignment]

if TYPE_CHECKING:
    from ._sockets import SocketAddress

T_Retval = TypeVar("T_Retval")
AsyncCallback: TypeAlias = "Task | Callable[[], Any]"
_current_event_loop: ContextVar[EventLoop] = ContextVar("current_event_loop")


class DelayedCallback:
    __slots__ = ("deadline", "callback")

    def __init__(self, deadline: float, callback: AsyncCallback):
        self.deadline = deadline
        self.callback = callback

    def __lt__(self, other: Any) -> bool:
        return self.deadline < other.deadline


def run(coro: Coroutine[Any, Any, T_Retval]) -> T_Retval:
    if _current_event_loop.get(None) is not None:
        raise RuntimeError("already running in an async event loop")

    return EventLoop().run_until_complete(coro)


class EventLoop:
    def __init__(self) -> None:
        from ._io_uring import IoUring

        # self._tasks: set[Task] = {}
        self._scheduled_callbacks: list[AsyncCallback] = []
        # self._delayed_callbacks: list[DelayedCallback] = []
        self._uring = IoUring()
        self._start_time = time.monotonic()

    def step(self) -> None:
        # print("\nstep() start")
        old_name, sniffio_thread_local.name = sniffio_thread_local.name, "asyncfusion"
        try:
            # Poll the uring, have it wait if there are no scheduled callbacks
            self._uring.poll(not bool(self._scheduled_callbacks))

            # Handle all the scheduled callbacks accumulated so far
            callbacks, self._scheduled_callbacks = self._scheduled_callbacks, []
            for callback in callbacks:
                if isinstance(callback, Task):
                    try:
                        value = callback._context.run(callback._coro.send, None)
                        # if callback._send_value is not empty:
                        #     send_value, callback._send_value = (
                        #         callback._send_value,
                        #         empty,
                        #     )
                        #     value = callback._context.run(
                        #         callback._coro.send, send_value
                        #     )
                        # else:
                        #     exception, callback._send_exception = (
                        #         callback._send_exception,
                        #         None,
                        #     )
                        #     assert exception is not None
                        #     value = callback._context.run(
                        #         callback._coro.throw,
                        #         type(exception),
                        #         exception,
                        #         exception.__traceback__,
                        #     )
                    except StopIteration as exc:  # task completed successfully
                        callback.set_result(exc.value)
                        continue
                    except BaseException as exc:  # task raised an error
                        callback.set_exception(exc)
                        continue

                    if isinstance(value, Future):
                        value.add_done_callback(
                            lambda future: self.reschedule_task(callback)
                        )
                    # if isinstance(value, Sleep):
                    #     if value.delay != infinite:
                    #         deadline = DelayedCallback(
                    #             self.current_time() + value.delay, callback
                    #         )
                    #         insort_right(self._delayed_callbacks, deadline)
                else:
                    callback()

            # Schedule any delayed callbacks for execution if their deadlines are
            # past the current time
            # _current_time = self.current_time()
            # while (
            #     self._delayed_callbacks
            #     and self._delayed_callbacks[0].deadline <= _current_time
            # ):
            #     callback = self._delayed_callbacks.pop(0)
            #     if isinstance(callback.callback, Task):
            #         callback.callback._send_value = None
            #
            #     self._scheduled_callbacks.append(callback.callback)
            #
            # # If there are no callbacks to handle, sleep until the first deadline
            # if not self._scheduled_callbacks and self._delayed_callbacks:
            #     time.sleep(self._delayed_callbacks[0].deadline - _current_time)
        finally:
            sniffio_thread_local.name = old_name

    def run_until_complete(self, coro: Coroutine[Any, Any, T_Retval]) -> T_Retval:
        self._uring.init()
        token = _current_event_loop.set(self)
        try:
            main_task = Task(coro, "Main task")
            self.reschedule_task(main_task)
            while not main_task.done():
                self.step()
        finally:
            _current_event_loop.reset(token)
            self._uring.close()

        return main_task.result()

    def run_forever(self) -> None:
        self._uring.init()
        token = _current_event_loop.set(self)
        try:
            while not self._closed:
                self.step()
        finally:
            _current_event_loop.reset(token)
            self._uring.close()

    def reschedule_task(self, task: Task) -> None:
        self._scheduled_callbacks.append(task)

    def time(self) -> float:
        return time.monotonic() - self._start_time

    def sleep(self, delay: float) -> Awaitable[Any]:
        if delay <= 0:
            future = Future()
            future.set_result(None)
            return future
        elif delay == infinite:
            return Future()

        return self._uring.sleep(delay)

    async def sock_accept(self, sock: socket) -> tuple[socket, SocketAddress]:
        sock_fd, addr = await self._uring.sock_accept(sock.fileno())
        return socket(sock.family, sock.type, sock.proto, sock_fd), addr

    async def sock_connect(self, sock: socket, address: SocketAddress) -> None:
        await self._uring.sock_connect(sock.fileno(), sock.family, address)

    async def sock_recv(self, sock: socket, max_bytes: int, flags: int = 0) -> bytes:
        return await self._uring.sock_recv(sock.fileno(), max_bytes, flags)

    async def sock_recv_into(self, sock: socket, buf: Buffer, flags: int = 0) -> bytes:
        return await self._uring.sock_recv_into(sock.fileno(), buf, flags)

    async def sock_recvfrom(
        self, sock: socket, max_bytes: int, flags: int = 0
    ) -> tuple[bytes, SocketAddress]:
        return await self._uring.sock_recvfrom(sock.fileno(), max_bytes, flags)

    async def sock_recvfrom_into(
        self, sock: socket, buf: Buffer, max_bytes: int = 0, flags: int = 0
    ) -> tuple[int, SocketAddress]:
        return await self._uring.sock_recvfrom_into(
            sock.fileno(), buf, max_bytes or len(buf), flags
        )

    async def sock_send(self, sock: socket, data: bytes, flags: int = 0) -> int:
        return await self._uring.sock_send(sock.fileno(), data, flags)

    async def sock_sendto(
        self, sock: socket, data: bytes, address: SocketAddress, flags: int = 0
    ) -> int:
        return await self._uring.sock_sendto(sock.fileno(), data, address, flags)

    async def sock_close(self, sock: socket) -> None:
        await self._uring.sock_close(sock.fileno())

    async def sock_wait_readable(self, sock: socket) -> None:
        await self._uring.sock_wait_readable(sock.fileno())

    async def sock_wait_writable(self, sock: socket) -> None:
        await self._uring.sock_wait_writable(sock.fileno())


def current_event_loop() -> EventLoop:
    try:
        return _current_event_loop.get()
    except LookupError:
        raise RuntimeError(
            "there is no asyncfusion event loop running in this thread"
        ) from None


def current_time() -> float:
    return current_event_loop().time()


def sleep(delay: float) -> Awaitable[T_Retval]:
    return current_event_loop().sleep(delay)
