from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from ._sync import CapacityLimiter

RetT = TypeVar("RetT")


async def run_sync(
    sync_fn: Callable[..., RetT],
    *args: object,
    thread_name: str | None = None,
    abandon_on_cancel: bool | None = None,
    cancellable: bool | None = None,
    limiter: CapacityLimiter | None = None,
) -> RetT:
    raise NotImplementedError


def current_default_thread_limiter() -> CapacityLimiter:
    raise NotImplementedError
