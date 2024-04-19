from __future__ import annotations

from asyncio import to_thread
from typing import Callable, ClassVar

from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    EVENT_TYPE: ClassVar[str] = "unknown"
    to_thread: bool = Field(False)

    @classmethod
    async def emit(cls, event_bus: EventBus, **kwargs) -> None:
        await event_bus.emit(cls(**kwargs))


class EventBus:
    def __init__(self) -> None:
        self._events: dict[str, list[Callable]] = {}

    def subscribe(self, event: type[BaseEvent], callback: Callable) -> None:
        if event.EVENT_TYPE not in self._events:
            self._events[event.EVENT_TYPE] = []
        self._events[event.EVENT_TYPE].append(callback)

    def unsubscribe(self, event: type[BaseEvent], callback: Callable) -> None:
        if event.EVENT_TYPE in self._events:
            self._events[event.EVENT_TYPE].remove(callback)
            if not self._events[event.EVENT_TYPE]:
                self._events.pop(event.EVENT_TYPE)

    async def emit(self, event: BaseEvent) -> None:
        if event.EVENT_TYPE in self._events:
            for callback in self._events[event.EVENT_TYPE]:
                if event.to_thread:
                    await to_thread(callback(event))
                else:
                    await callback(event)
