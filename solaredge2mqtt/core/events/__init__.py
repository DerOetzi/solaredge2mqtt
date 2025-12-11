from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from aiomqtt import MqttError

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger

Listener = Callable[[BaseEvent], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Listener]] = {}
        self._subscribed_events: dict[str, type[BaseEvent]] = {}
        self._tasks: set[asyncio.Task] = set()
        self._critical_error: BaseException | None = None

    def subscribe(
        self,
        event: type[BaseEvent] | list[type[BaseEvent]],
        listener: Listener,
    ) -> None:
        if isinstance(event, list):
            for _event in event:
                self.subscribe(_event, listener)
            return
        event_key = event.event_key()
        logger.info(f"Event subscribed: {event_key}")
        self._listeners.setdefault(event_key, []).append(listener)
        self._subscribed_events[event_key] = event

    @property
    def subscribed_events(self) -> list[type[BaseEvent]]:
        return list(self._subscribed_events.values())

    def unsubscribe(self, event: type[BaseEvent], listener: Listener) -> None:
        event_key = event.event_key()
        if event_key in self._listeners:
            try:
                self._listeners[event_key].remove(listener)
            except ValueError:
                pass
            if not self._listeners[event_key]:
                self._listeners.pop(event_key, None)
                self._subscribed_events.pop(event_key, None)

    def unsubscribe_all(self, event: type[BaseEvent]) -> None:
        event_key = event.event_key()
        if event_key in self._listeners:
            self._listeners.pop(event_key, None)
            self._subscribed_events.pop(event_key, None)

    async def emit(self, event: BaseEvent) -> None:
        if self._critical_error is not None:
            error = self._critical_error
            self._critical_error = None
            raise error

        event_key = event.event_key()
        logger.trace(f"Event emitted: {event_key}")
        listeners = self._listeners.get(event_key)
        if not listeners:
            return
        if event.AWAIT:
            await self._notify_listeners(event, listeners)
        else:
            task = asyncio.create_task(
                self._notify_listeners(event, listeners))
            self._tasks.add(task)
            task.add_done_callback(self._handle_task_done)

    async def _notify_listeners(
        self, event: BaseEvent, listeners: list[Listener]
    ) -> None:
        results = await asyncio.gather(
            *(self._notify_listener(listener, event)
              for listener in listeners),
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, (asyncio.CancelledError, MqttError)):
                raise r
            elif isinstance(r, Exception):
                logger.error("Unhandled listener error: {exc}", exc=repr(r))

    async def _notify_listener(self, listener: Listener, event: BaseEvent) -> None:
        try:
            await listener(event)
        except InvalidDataException as error:
            logger.warning("{message}, skipping this loop",
                           message=error.message)

    def _handle_task_done(self, task: asyncio.Task) -> None:
        self._tasks.discard(task)

        if task.cancelled():
            return

        exc = task.exception()
        if exc is None:
            return

        if isinstance(exc, MqttError):
            if self._critical_error is None:
                self._critical_error = exc
            else:
                logger.warning(
                    "New critical error occurred before previous was handled: {exc}",
                    exc=repr(exc),
                )
            return

        logger.error("Unhandled listener error: {exc}", exc=repr(exc))

    async def cancel_tasks(self) -> None:
        tasks = list(self._tasks)
        for t in tasks:
            t.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        self._tasks.clear()
        self._critical_error = None

        logger.info("Running tasks cancelled: {count}", count=len(tasks))
