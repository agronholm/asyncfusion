from __future__ import annotations

import socket
import sys
import time
import traceback
from bisect import insort_right
from collections.abc import Awaitable, Callable, Coroutine, Generator
from contextvars import ContextVar
from functools import partial
from traceback import print_tb
from types import SimpleNamespace, coroutine
from typing import Any, NoReturn, TYPE_CHECKING, TypeVar

from ._futures import Future
from ._tasks import Task
from ._utils import empty, infinite

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
                        value.add_done_callback(lambda future: self.reschedule_task(callback))
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

    # def _reschedule_task_from_future(self, task: Task, future: Future[Any]) -> None:
    #     assert future.done()
    #     if exc := future.exception():
    #         self.reschedule_task(task, exception=exc)
    #     else:
    #         self.reschedule_task(task, future.result())

    def reschedule_task(self, task: Task) -> None:
        # def reschedule_task(
        #     self, task: Task, value: object = empty, exception: BaseException | None = None
        # ) -> None:
        # if value is empty and exception is None:
        #     raise RuntimeError(
        #         f"INTERNAL ERROR: attempted to reschedule task {task.name} without a "
        #         f"value to send or exception to throw"
        #     )
        #
        # if task._send_value is not empty or task._send_exception is not None:
        #     raise RuntimeError(
        #         f"INTERNAL ERROR: attempted to reschedule task {task.name!r} which "
        #         f"already has a pending value or exception"
        #     )

        # task._send_value = value
        # task._send_exception = exception
        self._scheduled_callbacks.append(task)

    def time(self) -> float:
        return time.monotonic() - self._start_time

    def sleep(self, delay: float, result: T_Retval = None) -> Awaitable[Any]:
        if delay <= 0:
            future = Future[T_Retval]()
            future.set_result(result)
            return future
        elif delay == infinite:
            if result is not None:
                raise ValueError(
                    "sleep(math.inf) would never yield the result back to the task"
                )

            return Future[NoReturn]()

        return self._uring.sleep(delay, result)

    def sock_accept(self, fd: int) -> Awaitable[tuple[int, SocketAddress]]:
        return self._uring.sock_accept(fd)

    def sock_connect(self, fd: int, family: socket.AddressFamily, address: SocketAddress) -> Awaitable[None]:
        return self._uring.sock_connect(fd, family, address)

    def sock_recv(self, fd: int, max_bytes: int, flags: int = 0) -> Awaitable[bytes]:
        return self._uring.sock_recv(fd, max_bytes, flags)

    def sock_recvfrom(self, fd: int, max_bytes: int, flags: int = 0) -> Awaitable[tuple[bytes, SocketAddress]]:
        return self._uring.sock_recvfrom(fd, max_bytes, flags)

    def sock_send(self, fd: int, data: bytes, flags: int = 0) -> Awaitable[int]:
        return self._uring.sock_send(fd, data, flags)

    def sock_sendto(self, fd: int, data: bytes, address: SocketAddress, flags: int = 0) -> Awaitable[int]:
        return self._uring.sock_sendto(fd, data, address, flags)

    def sock_close(self, fd: int) -> Awaitable[None]:
        return self._uring.sock_close(fd)

    def sock_wait_readable(self, fd: int) -> Awaitable[None]:
        return self._uring.sock_wait_readable(fd)

    def sock_wait_writable(self, fd: int) -> Awaitable[None]:
        return self._uring.sock_wait_writable(fd)


# @coroutine
# def sleep(delay: float, /) -> Generator:
#     yield Sleep(delay)


def current_event_loop() -> EventLoop:
    try:
        return _current_event_loop.get()
    except LookupError:
        raise RuntimeError(
            "there is no asyncfusion event loop running in this thread"
        ) from None


def current_time() -> float:
    return current_event_loop().current_time()


def sleep(delay: float, result: T_Retval = None) -> Awaitable[T_Retval]:
    return current_event_loop().sleep(delay, result)
