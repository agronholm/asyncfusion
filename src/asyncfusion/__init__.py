from __future__ import annotations

from typing import Any

from ._eventloop import EventLoop as EventLoop
from ._eventloop import run as run
from ._eventloop import sleep as sleep
from ._eventloop import current_event_loop as current_event_loop
from ._eventloop import current_time as current_time
from ._exceptions import CancelledError as CancelledError
from ._exceptions import InvalidStateError as InvalidStateError
from ._importhook import install as install
from ._tasks import CancelScope as CancelScope
from ._tasks import Task as Task
from ._tasks import TaskGroup as TaskGroup
from ._sockets import AsyncSocket as AsyncSocket
from ._synchronization import CapacityLimiter as CapacityLimiter
from ._synchronization import Event as Event
from ._synchronization import Lock as Lock
from ._synchronization import Semaphore as Semaphore

# Re-export imports so they look like they live directly in this package
key: str
value: Any
for key, value in list(locals().items()):
    if getattr(value, "__module__", "").startswith(f"{__name__}."):
        value.__module__ = __name__
