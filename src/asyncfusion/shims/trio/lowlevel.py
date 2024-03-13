from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import asyncfusion

if TYPE_CHECKING:
    from ._tasks import Nursery


@dataclass
class RunStatistics:
    tasks_living: int
    tasks_runnable: int
    seconds_to_next_deadline: float
    run_sync_soon_queue_size: int
    io_statistics: object


class Clock:
    pass


class Task:
    def __init__(self, original: asyncfusion.Task):
        self._original = original

    @property
    def name(self) -> str:
        return self._original.name

    @name.setter
    def name(self, value: object) -> None:
        self._original.name = value

    @property
    def context(self) -> str:
        return self._original._context

    @property
    def parent_nursery(self) -> Nursery:
        return self._original._parent_task_group

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Task):
            return self._original == other._original

        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._original)


def current_statistics() -> RunStatistics:
    raise NotImplementedError


def current_clock() -> Clock:
    raise NotImplementedError


def current_root_task() -> Task:
    raise NotImplementedError


def current_task() -> Task:
    raise NotImplementedError
