from __future__ import annotations


class Empty:
    __slots__ = ()

    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "Empty()"


empty = Empty()  # sentinel, to be used where None is a valid value too
infinite = float("inf")
