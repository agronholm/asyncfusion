from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Coroutine
from contextlib import asynccontextmanager
from typing import Any, Protocol, TypeVar

import asyncfusion

from .lowlevel import Task

StatusT_contra = TypeVar("StatusT_contra", contravariant=True)


class Nursery:
    def __init__(self, task_group: asyncfusion.TaskGroup):
        self._task_group = task_group

    async def start(
        self,
        async_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        name: object,
    ) -> Any:
        raise NotImplementedError

    def start_soon(
        self,
        async_fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
        name: object,
    ) -> None:
        self._task_group.create_task(async_fn(*args), name=name)

    @property
    def cancel_scope(self) -> asyncfusion.CancelScope:
        return self._task_group.cancel_scope

    @property
    def child_tasks(self) -> frozenset[Task]:
        raise NotImplementedError

    @property
    def parent_task(self) -> Task:
        raise NotImplementedError


class TaskStatus(Protocol[StatusT_contra]):
    def started(self, value: StatusT_contra) -> None:
        raise NotImplementedError


class _TaskStatusIgnored(TaskStatus[Any]):
    def __repr__(self) -> str:
        return "TASK_STATUS_IGNORED"

    def started(self, value: Any = None) -> None:
        pass


TASK_STATUS_IGNORED = _TaskStatusIgnored()


@asynccontextmanager
async def open_nursery() -> AsyncGenerator[Nursery, Any]:
    async with asyncfusion.TaskGroup() as task_group:
        yield Nursery(task_group)
