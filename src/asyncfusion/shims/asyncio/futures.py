from __future__ import annotations

import sys
from collections.abc import Callable
from contextvars import Context
from typing import Any, Generic, NamedTuple, TypeVar

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T_Retval = TypeVar("T_Retval")


class FutureCallback(NamedTuple):
    callback: Callable[[Future], Any]
    context: Context | None


class Future(Generic[T_Retval]):
    __slots__ = ("_done", "_result", "_exception")

    _result: T_Retval

    def __init__(self) -> None:
        self._callbacks: list[FutureCallback] = []
        self._done: bool = False
        self._exception: BaseException | None = None

    def done(self) -> bool:
        return self._exception is not None or hasattr(self, "_result")

    def result(self) -> T_Retval:
        if self._exception is not None:
            raise self._exception

        return self._result

    def exception(self) -> BaseException | None:
        return self._exception

    def set_result(self, result: T_Retval) -> None:
        self._done = True
        self._result = result
        for callback in self._callbacks:
            if callback.context:
                callback.context.run(callback.callback, self)
            else:
                callback.callback(self)

        self._callbacks.clear()

    def set_exception(self, exception: BaseException) -> None:
        self._done = True
        self._exception = exception
        for callback in self._callbacks:
            if callback.context:
                callback.context.run(callback.callback, self)
            else:
                callback.callback(self)

        self._callbacks.clear()

    def add_done_callback(
        self, callback: Callable[[Self], Any], *, context: Context | None = None
    ) -> None:
        self._callbacks.append(FutureCallback(callback, context))

    def remove_done_callback(self, callback: Callable[[Future], Any]) -> int:
        raise NotImplementedError
