from __future__ import annotations

import sys
from collections.abc import Coroutine
from contextvars import Context, ContextVar, copy_context
from itertools import count
from types import TracebackType
from typing import Any, Generic, TypeVar

from ._exceptions import CancelledError
from ._futures import Future
from ._utils import empty

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from exceptiongroup import BaseExceptionGroup
    from typing_extensions import Self

T_Retval = TypeVar("T_Retval")
_current_task: ContextVar[Task] = ContextVar("current_task")
task_counter = count(1)


class Task(Future):
    _name: str
    _coro: Coroutine[Any, Any, T_Retval]
    _parent_task_group: TaskGroup | None
    # _cancel_scope: CancelScope
    _context: Context
    _send_value: object = empty
    _send_exception: BaseException | None = None

    def __init__(
        self,
        coro: Coroutine[Any, Any, T_Retval],
        name: str,
        parent_task_group: TaskGroup | None = None,
    ):
        super().__init__()
        self._coro = coro
        self.name = name
        self._parent_task_group = parent_task_group
        self._context = copy_context()
        self._context.run(_current_task.set, self)

    def cancel(self, message: str | None = None) -> None:
        self._send_exception = CancelledError(message)

    @property
    def coro(self) -> Coroutine[Any, Any, T_Retval]:
        return self._coro

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: object) -> None:
        self._name = str(value)


class CancelScope:
    def __init__(self) -> None:
        self._children: list[CancelScope] = []
        self._tasks: set[Task] = set()
        self.shield: bool = False

    def cancel(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        return None


class TaskGroup:
    _entered: bool = False
    _closed: bool = False

    def __init__(self) -> None:
        from ._synchronization import Event

        self._tasks = set[Task]()
        self._cancel_scope = CancelScope()
        self._exceptions: list[BaseException] = []
        self._exit_event = Event()

    def create_task(
        self, coro: Coroutine[Any, Any, T_Retval], name: object = None
    ) -> Task[T_Retval]:
        from asyncfusion._eventloop import current_event_loop

        if not self._entered:
            raise RuntimeError("this task group has not been entered yet")

        task = Task(coro, str(name) if name else f"Task-{next(task_counter)}", self)
        current_event_loop().reschedule_task(task, None)
        self._tasks.add(task)
        task.add_done_callback(self._task_done)
        return task

    def _task_done(self, task: Task[Any]) -> None:
        self._tasks.remove(task)
        if exc := task.exception():
            self._exceptions.append(exc)
            self._cancel_scope.cancel()
            self._exit_event.set()
        elif not self._tasks:
            self._exit_event.set()

    @property
    def cancel_scope(self) -> CancelScope:
        return self._cancel_scope

    async def __aenter__(self) -> Self:
        self._cancel_scope.__enter__()
        if self._closed:
            raise RuntimeError("this task group has already been closed")
        elif self._entered:
            raise RuntimeError("this task group has already been entered")

        self._entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        from ._synchronization import Event

        self._closed = True
        if exc_val is not None:
            self._exceptions.append(exc_val)
            self._cancel_scope.cancel()

        while self._tasks:
            await self._exit_event.wait()
            self._exit_event = Event()

        if self._exceptions:
            raise BaseExceptionGroup("", self._exceptions)

        return None
