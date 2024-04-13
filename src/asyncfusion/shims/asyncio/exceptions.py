from __future__ import annotations

from builtins import TimeoutError as TimeoutError

from ..._exceptions import CancelledError as CancelledError


class InvalidStateError(Exception):
    pass


class SendfileNotAvailableError(Exception):
    pass


class IncompleteReadError(Exception):
    def __init__(self, partial: bytes, expected: int | None) -> None:
        r_expected = "undefined" if expected is None else repr(expected)
        super().__init__(
            f"{len(partial)} bytes read on a total of " f"{r_expected} expected bytes"
        )
        self.partial = partial
        self.expected = expected


class LimitOverrunError(Exception):
    def __init__(self, message: str, consumed: int) -> None:
        super().__init__(message)
        self.consumed = consumed
