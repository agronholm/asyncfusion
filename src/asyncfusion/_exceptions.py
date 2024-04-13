from __future__ import annotations


class InvalidStateError(Exception):
    pass


class CancelledError(BaseException):
    def __init__(self, message: str | None = None):
        super().__init__(message)
