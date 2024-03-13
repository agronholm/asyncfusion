from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from ._eventloop import TrioToken

RetT = TypeVar("RetT")


def run(
    afn: Callable[..., Awaitable[RetT]],
    *args: object,
    trio_token: TrioToken | None = None,
) -> RetT:
    raise NotImplementedError


def check_cancelled() -> None:
    raise NotImplementedError
