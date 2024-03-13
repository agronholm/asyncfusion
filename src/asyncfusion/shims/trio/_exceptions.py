from __future__ import annotations

from asyncfusion import _exceptions

TooSlowError = TimeoutError
Cancelled = _exceptions.CancelledError


class NeedHandshakeError(Exception):
    pass
