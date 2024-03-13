from __future__ import annotations

from builtins import TimeoutError as TimeoutError

from ..._exceptions import CancelledError as CancelledError


class InvalidStateError(Exception):
    pass


class SendfileNotAvailableError(Exception):
    pass


class IncompleteReadError(Exception):
    pass


class LimitOverrunError(Exception):
    pass
