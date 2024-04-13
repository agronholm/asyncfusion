from __future__ import annotations

import sys
from collections.abc import Callable
from contextvars import copy_context
from functools import partial
from typing import TypeVar

from .events import get_running_loop

if sys.version_info >= (3, 11):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

P = ParamSpec("P")
T_Retval = TypeVar("T_Retval")


async def to_thread(
    func: Callable[P, T_Retval], /, *args: P.args, **kwargs: P.kwargs
) -> T_Retval:
    loop = get_running_loop()
    ctx = copy_context()
    func_call = partial(ctx.run, func, *args, **kwargs)
    return await loop.run_in_executor(None, func_call)
