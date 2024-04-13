from __future__ import annotations

from collections.abc import Coroutine
from contextvars import Context
from typing import Any, TypeVar, final

T_Retval = TypeVar("T_Retval")


@final
class Runner:
    def __init__(self, *, debug: bool | None = None):
        self.debug = debug

    def run(
        self, coro: Coroutine[Any, Any, T_Retval], *, context: Context | None = None
    ) -> T_Retval:
        raise NotImplementedError


def run(
    main: Coroutine[Any, Any, T_Retval],
    *,
    debug: bool | None = None,
    loop_factory: Any = None,
) -> T_Retval:
    if loop_factory is not None:
        raise NotImplementedError(
            "the loop_factory parameter is not supported in AsyncFusion"
        )

    return Runner().run(main)
