from typing import Callable
from asyncio import to_thread


class EventBus:
    def __init__(self) -> None:
        self._events: dict[str, list[Callable]] = {}

    def subscribe(self, event: str, callback: Callable) -> None:
        if event not in self._events:
            self._events[event] = []
        self._events[event].append(callback)

    def unsubscribe(self, event: str, callback: Callable) -> None:
        if event in self._events:
            self._events[event].remove(callback)
            if not self._events[event]:
                self._events.pop(event)

    async def publish(self, event: str, *args, **kwargs) -> None:
        if event in self._events:
            for callback in self._events[event]:
                await to_thread(callback(*args, **kwargs))
