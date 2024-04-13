from __future__ import annotations

from asyncfusion import _exceptions

TooSlowError = TimeoutError
Cancelled = _exceptions.CancelledError


class NeedHandshakeError(Exception):
    pass


class WouldBlock(Exception):
    pass


class BusyResourceError(Exception):
    pass


class ClosedResourceError(Exception):
    pass


class BrokenResourceError(Exception):
    pass
