from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from contextvars import Context
from typing import Any, Generic, NamedTuple, TypeVar

from ._exceptions import InvalidStateError

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T_Retval = TypeVar("T_Retval")


class FutureCallback(NamedTuple):
    callback: Callable[[Future], Any]
    context: Context | None

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, FutureCallback):
            return self.callback == other.callback

        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.callback)


class Future(Generic[T_Retval]):
    __slots__ = ("_callbacks", "_done", "_result", "_exception")

    _result: T_Retval

    def __init__(self) -> None:
        self._callbacks: list[FutureCallback] = []
        self._done: bool = False
        self._exception: BaseException | None = None

    def done(self) -> bool:
        return self._exception is not None or hasattr(self, "_result")

    def result(self) -> T_Retval:
        if not self._done:
            raise InvalidStateError(f"This {self.__class__.__name__} is not done yet")

        if self._exception is not None:
            raise self._exception

        return self._result

    def exception(self) -> BaseException | None:
        if not self._done:
            raise InvalidStateError(f"This {self.__class__.__name__} is not done yet")

        return self._exception

    def _run_callbacks(self) -> None:
        for callback in self._callbacks:
            if callback.context:
                callback.context.run(callback.callback, self)
            else:
                callback.callback(self)

        self._callbacks.clear()

    def set_result(self, result: T_Retval) -> None:
        if self._done:
            raise InvalidStateError(f"This {self.__class__.__name__} is already done")

        self._done = True
        self._result = result
        self._run_callbacks()

    def set_exception(self, exception: BaseException) -> None:
        if self._done:
            raise InvalidStateError(f"This {self.__class__.__name__} is already done")

        self._done = True
        self._exception = exception
        self._run_callbacks()

    def add_done_callback(
        self, callback: Callable[[Self], Any], *, context: Context | None = None
    ) -> None:
        self._callbacks.append(FutureCallback(callback, context))
        if self._done:
            self._run_callbacks()

    def remove_done_callback(self, callback: Callable[[Future], Any]) -> int:
        try:
            self._callbacks.remove(FutureCallback(callback, None))
        except ValueError:
            return 0

        return 1

    def __await__(self) -> Iterator[Self]:
        yield self
        return self.result()

# from typing import Generic, TypeVar
#
# from ._eventloop import _current_event_loop, sleep
# from ._tasks import _current_task
#
# T = TypeVar("T")
#
#
# class Future(Generic[T]):
#     __slots__ = "_task"
#
#     def set_result(self, result: T) -> None:
#         _current_event_loop.get().reschedule_task(self._task, result)
#
#     def set_exception(self, exception: BaseException) -> None:
#         _current_event_loop.get().reschedule_task(self._task, exception=exception)
#
#     def __await__(self):
#         self._task = _current_task.get()
#         return sleep(float("inf"))
