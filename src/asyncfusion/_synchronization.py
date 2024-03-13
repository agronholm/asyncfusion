from __future__ import annotations

import sys
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
from types import TracebackType

from ._eventloop import current_event_loop, sleep
from ._tasks import Task, _current_task
from ._utils import infinite

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Event:
    __slots__ = "_flag", "_subscribers"

    def __init__(self) -> None:
        self._flag = False
        self._subscribers: list[Task] = []

    def is_set(self) -> bool:
        return self._flag

    def set(self) -> None:
        if self._flag:
            return

        loop = current_event_loop()
        for task in self._subscribers:
            loop.reschedule_task(task, None)

        self._subscribers.clear()

    async def wait(self) -> None:
        if self._flag:
            return

        self._subscribers.append(_current_task.get())
        await sleep(infinite)

    def statistics(self) -> EventStatistics:
        return EventStatistics(tasks_waiting=len(self._subscribers))


@dataclass(frozen=True)
class EventStatistics:
    tasks_waiting: int


class CapacityLimiter:
    __slots__ = ("_total_tokens", "_owner", "_borrowers", "_waiters")

    _total_tokens: int

    def __init__(self, total_tokens: int) -> None:
        self.total_tokens = total_tokens
        self._borrowers = deque[object]()
        self._waiters = deque[Task]()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()

    def acquire_nowait(self) -> None:
        return self.acquire_on_behalf_of_nowait(_current_task.get())

    def acquire_on_behalf_of_nowait(self, borrower: object) -> None:
        raise NotImplementedError

    async def acquire(self) -> None:
        return await self.acquire_on_behalf_of(_current_task.get())

    async def acquire_on_behalf_of(self, borrower: object) -> None:
        raise NotImplementedError

    def release(self) -> None:
        self.release_on_behalf_of(_current_task.get())

    def release_on_behalf_of(self, borrower: object) -> None:
        raise NotImplementedError

    def statistics(self) -> CapacityLimiterStatistics:
        return CapacityLimiterStatistics(
            borrowed_tokens=self._borrowed_tokens,
            total_tokens=self._total_tokens,
            borrowers=list(self._borrowers),
            tasks_waiting=len(self._borrowers),
        )

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @total_tokens.setter
    def total_tokens(self, value: int) -> None:
        if not isinstance(value, int):
            raise TypeError("value must be an integer")
        elif value < 1:
            raise ValueError("value must be a positive integer")

        # Notify an appropriate number of waiters if the capacity increases
        if value > self._total_tokens:
            event_loop = current_event_loop.get()
            for _ in range(value - self._total_tokens):
                task = self._waiters.popleft()
                event_loop.reschedule_task(task, None)

        self._total_tokens = value

    @property
    def borrowed_tokens(self) -> int:
        return len(self._borrowers)

    @property
    def available_tokens(self) -> float:
        return self._total_tokens - len(self._borrowers)


@dataclass(frozen=True)
class CapacityLimiterStatistics:
    borrowed_tokens: int
    total_tokens: int
    borrowers: Sequence[Task]
    tasks_waiting: int


class Semaphore:
    pass


@dataclass(frozen=True)
class SemaphoreStatistics:
    pass


class Lock:
    pass


@dataclass(frozen=True)
class LockStatistics:
    pass
