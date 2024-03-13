from __future__ import annotations


class CancelledError(BaseException):
    def __init__(self, message: str | None = None):
        super().__init__(message)


class InvalidStateError(Exception):
    pass
