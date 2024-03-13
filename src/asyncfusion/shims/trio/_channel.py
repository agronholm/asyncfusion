from __future__ import annotations

import sys
from collections import deque
from dataclasses import dataclass, field
from types import TracebackType
from typing import TYPE_CHECKING, Generic, TypeVar

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from .lowlevel import Task

T = TypeVar("T")


@dataclass(frozen=True)
class MemoryChannelStats:
    current_buffer_used: int
    max_buffer_size: int | float
    open_send_channels: int
    open_receive_channels: int
    tasks_waiting_send: int
    tasks_waiting_receive: int


@dataclass
class MemoryChannelState(Generic[T]):
    max_buffer_size: float
    data: deque[T] = field(init=False, default_factory=deque)
    open_send_channels: int = field(init=False, default=0)
    open_receive_channels: int = field(init=False, default=0)
    send_tasks: dict[Task, T] = field(init=False, default_factory=dict)
    receive_tasks: dict[Task, None] = field(init=False, default_factory=dict)

    def statistics(self) -> MemoryChannelStats:
        return MemoryChannelStats(
            current_buffer_used=len(self.data),
            max_buffer_size=self.max_buffer_size,
            open_send_channels=self.open_send_channels,
            open_receive_channels=self.open_receive_channels,
            tasks_waiting_send=len(self.send_tasks),
            tasks_waiting_receive=len(self.receive_tasks),
        )


@dataclass(frozen=True)
class MemorySendChannel(Generic[T]):
    state: MemoryChannelState

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def clone(self) -> MemorySendChannel[T]:
        raise NotImplementedError

    def statistics(self) -> MemoryChannelStats:
        return self.state.statistics()

    async def aclose(self) -> None:
        self.close()

    def close(self) -> None:
        pass

    async def send(self, value: T) -> None:
        raise NotImplementedError

    def send_nowait(self, value: T) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class MemoryReceiveChannel(Generic[T]):
    state: MemoryChannelState

    def clone(self) -> MemoryReceiveChannel[T]:
        raise NotImplementedError

    def statistics(self) -> MemoryChannelStats:
        return self.state.statistics()

    async def aclose(self) -> None:
        self.close()

    def close(self) -> None:
        raise NotImplementedError

    async def receive(self) -> T:
        raise NotImplementedError

    def receive_nowait(self) -> T:
        raise NotImplementedError


if TYPE_CHECKING:

    class open_memory_channel(Generic[T]):
        def __init__(self, max_buffer_size: float):
            pass

        def __call__(self) -> tuple[MemorySendChannel[T], MemoryReceiveChannel[T]]:
            pass
else:

    def open_memory_channel(
        max_buffer_size: float,
    ) -> tuple[MemorySendChannel, MemoryReceiveChannel]:
        state = MemoryChannelState(max_buffer_size)
        return MemorySendChannel(state), MemoryReceiveChannel(state)
