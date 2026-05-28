from __future__ import annotations

import asyncio
from typing import (
    Any,
    Awaitable,
    Callable,
    ClassVar,
    Protocol,
    TypeVar,
    cast,
    overload,
)

from aiomqtt import MqttError

from solaredge2mqtt.core.events.events import BaseEvent, TEvent, TEventContra
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger

_EVENT_SUBSCRIPTIONS_ATTR = "_event_subscriptions"


class Listener(Protocol[TEventContra]):
    def __call__(self, event: TEventContra) -> Awaitable[None]: ...  # pragma: no cover


AnyListener = Listener[Any]
TInstance = TypeVar("TInstance")
ListenerMethod = Callable[[TInstance, TEvent], Awaitable[None]]
ListenerDecorator = Callable[
    [ListenerMethod[TInstance, TEvent]], ListenerMethod[TInstance, TEvent]
]


class EventBus:
    _listeners: ClassVar[dict[str, list[Listener[Any]]]] = {}
    _subscribed_events: ClassVar[dict[str, type[BaseEvent]]] = {}
    _tasks: ClassVar[set[asyncio.Task]] = set()
    _critical_error: ClassVar[BaseException | None] = None

    @overload
    @classmethod
    def subscribe(
        cls,
        event: type[TEvent] | list[type[TEvent]],
        listener: Listener[TEvent],
    ) -> None: ...  # pragma: no cover

    @overload
    @classmethod
    def subscribe(
        cls,
        event: type[TEvent] | list[type[TEvent]],
    ) -> ListenerDecorator[TInstance, TEvent]: ...  # pragma: no cover

    @classmethod
    def subscribe(
        cls,
        event: type[TEvent] | list[type[TEvent]],
        listener: Listener[TEvent] | None = None,
    ) -> ListenerDecorator[TInstance, TEvent] | None:
        if listener is not None:
            cls._do_subscribe(event, listener)
            return None

        def decorator(
            method: ListenerMethod[TInstance, TEvent],
        ) -> ListenerMethod[TInstance, TEvent]:
            events = event if isinstance(event, list) else [event]
            existing: list[type[BaseEvent]] = getattr(
                method, _EVENT_SUBSCRIPTIONS_ATTR, []
            )
            setattr(method, _EVENT_SUBSCRIPTIONS_ATTR, existing + events)
            return method

        return decorator

    @classmethod
    def _do_subscribe(
        cls,
        event: type[TEvent] | list[type[TEvent]],
        listener: Listener[TEvent],
    ) -> None:
        if isinstance(event, list):
            for evt in event:
                cls._do_subscribe(evt, listener)
            return

        event_key = event.event_key()
        logger.info(f"Event subscribed: {event_key}")
        cls._listeners.setdefault(event_key, []).append(cast(AnyListener, listener))
        cls._subscribed_events[event_key] = event

    @classmethod
    def register(cls, instance: Any) -> None:
        for name in dir(type(instance)):
            method = getattr(type(instance), name, None)
            subscriptions: list[type[BaseEvent]] = getattr(
                method, _EVENT_SUBSCRIPTIONS_ATTR, []
            )
            if subscriptions:
                bound_method = getattr(instance, name)
                cls._do_subscribe(subscriptions, bound_method)

    @classmethod
    def subscribed_events(cls) -> set[type[BaseEvent]]:
        return set(cls._subscribed_events.values())

    @overload
    @classmethod
    def unsubscribe(
        cls,
        event: TEvent,
        listener: Callable[[TEvent], Awaitable[None]],
    ) -> None: ...  # pragma: no cover

    @overload
    @classmethod
    def unsubscribe(
        cls,
        event: type[TEvent],
        listener: Callable[[TEvent], Awaitable[None]],
    ) -> None: ...  # pragma: no cover

    @classmethod
    def unsubscribe(
        cls,
        event: TEvent | type[TEvent],
        listener: Callable[[TEvent], Awaitable[None]],
    ) -> None:
        event_key = event.event_key()
        if event_key in cls._listeners:
            try:
                cls._listeners[event_key].remove(cast(AnyListener, listener))
            except ValueError:
                pass

            if len(cls._listeners[event_key]) == 0:
                cls._listeners.pop(event_key, None)
                cls._subscribed_events.pop(event_key, None)

    @classmethod
    def unsubscribe_all(cls, event: type[TEvent]) -> None:
        event_key = event.event_key()
        if event_key in cls._listeners:
            cls._listeners.pop(event_key, None)
            cls._subscribed_events.pop(event_key, None)

    @classmethod
    async def emit(cls, event: BaseEvent) -> None:
        if cls._critical_error is not None:
            error = cls._critical_error
            cls._critical_error = None
            raise error

        event_key = event.event_key()
        logger.trace(f"Event emitted: {event_key}")
        listeners = cls._resolve_listeners(type(event))
        if not listeners:
            return
        if event.AWAIT:
            await cls._notify_listeners(event, listeners)
        else:
            task = asyncio.create_task(cls._notify_listeners(event, listeners))
            cls._tasks.add(task)
            task.add_done_callback(cls._handle_task_done)

    @classmethod
    def _resolve_listeners(cls, event_type: type[BaseEvent]) -> list[AnyListener]:
        listeners: list[AnyListener] = []
        seen_listeners: set[int] = set()

        for klass in event_type.__mro__:
            if not issubclass(klass, BaseEvent):
                continue
            event_key = klass.event_key()
            for listener in cls._listeners.get(event_key, []):
                listener_id = id(listener)
                if listener_id in seen_listeners:
                    continue

                seen_listeners.add(listener_id)
                listeners.append(listener)

        return listeners

    @classmethod
    async def _notify_listeners(
        cls, event: BaseEvent, listeners: list[AnyListener]
    ) -> None:
        results = await asyncio.gather(
            *(cls._notify_listener(listener, event) for listener in listeners),
            return_exceptions=True,
        )

        for r in results:
            if isinstance(r, (asyncio.CancelledError, MqttError)):
                raise r
            elif isinstance(r, Exception):
                logger.error("Unhandled listener error: {exc}", exc=repr(r))

    @classmethod
    async def _notify_listener(cls, listener: AnyListener, event: BaseEvent) -> None:
        try:
            await listener(event)
        except InvalidDataException as error:
            logger.warning("{message}, skipping this loop", message=error.message)

    @classmethod
    def _handle_task_done(cls, task: asyncio.Task) -> None:
        cls._tasks.discard(task)

        if task.cancelled():
            return

        exc = task.exception()
        if exc is None:
            return

        if isinstance(exc, MqttError):
            if cls._critical_error is None:
                cls._critical_error = exc
            else:
                logger.warning(
                    "New critical error occurred before previous was handled: {exc}",
                    exc=repr(exc),
                )
            return

        logger.error("Unhandled listener error: {exc}", exc=repr(exc))

    @classmethod
    async def cancel_tasks(cls) -> None:
        tasks = list(cls._tasks)
        for t in tasks:
            t.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        cls._tasks.clear()
        cls._critical_error = None

        logger.info("Running tasks cancelled: {count}", count=len(tasks))
