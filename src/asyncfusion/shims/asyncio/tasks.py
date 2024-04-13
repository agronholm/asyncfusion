from __future__ import annotations

import sys
from collections.abc import Awaitable, Coroutine, Generator, Iterable, Iterator
from typing import Any, Generic, TypeVar, Union, overload

import asyncfusion

from .futures import Future

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

_T = TypeVar("_T")
_FutureLike: TypeAlias = Union[Future[_T], Generator[Any, None, _T], Awaitable[_T]]


def as_completed(
    fs: Iterable[_FutureLike[_T]], *, timeout: float | None = None
) -> Iterator[Future[_T]]:
    raise NotImplementedError


def shield(arg: _FutureLike[_T]) -> Future[_T]:
    raise NotImplementedError


@overload
async def sleep(delay: float, result: _T) -> _T: ...


@overload
async def sleep(delay: float) -> None: ...


async def sleep(delay: float, result: _T | None = None) -> _T | None:
    await asyncfusion.sleep(delay)
    return result


async def wait_for(fut: _FutureLike[_T], timeout: float | None) -> _T:
    raise NotImplementedError


class Task(Generic[_T], asyncfusion.Task[_T]):
    def get_coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    def get_name(self) -> str:
        return self.name

    def set_name(self, name: object) -> None:
        self.name = str(name)
