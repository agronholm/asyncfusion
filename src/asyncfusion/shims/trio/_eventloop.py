from __future__ import annotations

import sys
from collections.abc import Callable, Coroutine
from contextvars import ContextVar
from typing import Any, TypeVar

import asyncfusion

if sys.version_info >= (3, 11):
    from typing import TypeVarTuple, Unpack
else:
    from typing_extensions import TypeVarTuple, Unpack

T_Retval = TypeVar("T_Retval")
PosArgsT = TypeVarTuple("PosArgsT")
_current_trio_token: ContextVar[TrioToken] = ContextVar("_current_trio_token")

current_time = asyncfusion.current_time
sleep = asyncfusion.sleep


class TrioToken:
    __slots__ = "_event_loop"

    def __init__(self, event_loop: asyncfusion.EventLoop):
        self._event_loop = event_loop

    def run_sync_soon(
        self,
        sync_fn: Callable[[Unpack[PosArgsT]], object],
        *args: Unpack[PosArgsT],
        idempotent: bool = False,
    ) -> None:
        raise NotImplementedError


def run(callback: Callable[..., Coroutine[Any, Any, T_Retval]]) -> T_Retval:
    return asyncfusion.run(callback())


def current_trio_token() -> TrioToken:
    try:
        return _current_trio_token.get()
    except LookupError:
        try:
            loop = asyncfusion.current_event_loop.get()
        except LookupError:
            raise RuntimeError("must be called from async context")

        trio_token = TrioToken(loop)
        _current_trio_token.set(trio_token)
        return trio_token


async def sleep_until(deadline: float) -> None:
    await sleep(max(deadline - current_time(), 0))


async def sleep_forever() -> None:
    await sleep(float("inf"))
