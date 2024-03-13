from __future__ import annotations

import sys
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar, overload

import asyncfusion

if sys.version_info >= (3, 11):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

P = ParamSpec("P")
T_Retval = TypeVar("T_Retval")


class AbstractEventLoop:
    pass


class AsyncFusionEventLoop(AbstractEventLoop):
    def __init__(self, event_loop: asyncfusion.EventLoop):
        self._event_loop = event_loop


def run(
    coro: Coroutine[Any, Any, T_Retval],
    *,
    debug: bool | None = None,
    loop_factory: Any = None,
) -> T_Retval:
    if loop_factory is not None:
        raise NotImplementedError(
            "the loop_factory parameter is not supported in AsyncFusion"
        )

    return asyncfusion.run(coro)


def get_running_loop() -> AbstractEventLoop:
    raise NotImplementedError


def get_event_loop() -> AbstractEventLoop:
    try:
        return get_running_loop()
    except RuntimeError:
        raise NotImplementedError(
            "using get_event_loop() to create a new event loop is not supported in "
            "AsyncFusion"
        ) from None


def set_event_loop(loop: AbstractEventLoop) -> None:
    raise NotImplementedError("this function is not supported in AsyncFusion")


def new_event_loop(loop: AbstractEventLoop) -> None:
    raise NotImplementedError("this function is not supported in AsyncFusion")


@overload
async def sleep(delay: float, result: T_Retval) -> T_Retval:
    ...


@overload
async def sleep(delay: float) -> None:
    ...


async def sleep(delay: float, result: T_Retval | None = None) -> T_Retval | None:
    await asyncfusion.sleep(delay)
    return result


async def to_thread(
    func: Callable[P, T_Retval], /, *args: P.args, **kwargs: P.kwargs
) -> T_Retval:
    raise NotImplementedError


class Task(asyncfusion.Task):
    def get_coro(self) -> Coroutine[Any, Any, Any]:
        return self._coro

    def get_name(self) -> str:
        return self.name

    def set_name(self, name: object) -> None:
        self.name = str(name)


# class TaskGroup(_core.TaskGroup):
