"""Tests for core EventBus module."""

import asyncio

import pytest
from aiomqtt import MqttError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.exceptions import InvalidDataException


class LoggerSpy:
    def __init__(self):
        self.infos = []
        self.traces = []
        self.warnings = []
        self.errors = []

    def info(self, message, **kwargs):
        self.infos.append((message, kwargs))

    def trace(self, message, **kwargs):
        self.traces.append((message, kwargs))

    def warning(self, message, **kwargs):
        self.warnings.append((message, kwargs))

    def error(self, message, **kwargs):
        self.errors.append((message, kwargs))


class TestEvent(BaseEvent):
    """Test event class."""


class AwaitingTestEvent(BaseEvent):
    """Test event with AWAIT=True."""

    AWAIT = True


class NonAwaitingTestEvent(BaseEvent):
    """Test event with default AWAIT=False semantics."""


class ChildTestEvent(TestEvent):
    """Concrete child event used to validate base-class subscriptions."""

    AWAIT = True


class ListenerOwner:
    """Helper class with async bound listener method for deduplication tests."""

    def __init__(self) -> None:
        self.received_events: list[BaseEvent] = []

    async def my_listener(self, event: BaseEvent) -> None:
        await asyncio.sleep(0)
        self.received_events.append(event)


class TestEventBus:
    """Tests for EventBus class."""

    def test_subscribe_single_event(self, event_bus):
        """Test subscribing to a single event."""

        def listener(event):
            """Stub listener for subscription test - not invoked."""
            del event

        event_bus.subscribe(TestEvent, listener)
        listeners = event_bus.subscribed_events
        assert TestEvent in listeners

    def test_subscribe_multiple_events(self, event_bus):
        """Test subscribing to multiple events at once."""

        def listener(event):
            """Stub listener for subscription test - not invoked."""
            del event

        class AnotherEvent(BaseEvent):
            """Another test event."""

        event_bus.subscribe([TestEvent, AnotherEvent], listener)
        events = event_bus.subscribed_events
        assert TestEvent in events
        assert AnotherEvent in events

    def test_subscribed_events_property(self, event_bus):
        """Test subscribed_events property returns correct events."""

        def listener(event):
            """Stub listener for subscription test - not invoked."""
            del event

        event_bus.subscribe(TestEvent, listener)

        events = event_bus.subscribed_events
        assert TestEvent in events

    def test_unsubscribe(self, event_bus):
        """Test unsubscribing from an event."""

        def listener(event):
            """Stub listener for unsubscribe test - not invoked."""
            del event

        event_bus.subscribe(TestEvent, listener)
        event_bus.unsubscribe(TestEvent, listener)

        events = event_bus.subscribed_events
        assert TestEvent not in events

    @pytest.mark.asyncio
    async def test_unsubscribe_does_not_remove_base_subscription_for_child(
        self, event_bus
    ):
        """Unsubscribing child event must not remove base-event subscriptions."""
        received_events = []

        async def listener(event):
            await asyncio.sleep(0)
            received_events.append(event)

        event_bus.subscribe(TestEvent, listener)
        event_bus.unsubscribe(ChildTestEvent, listener)

        await event_bus.emit(ChildTestEvent())

        assert len(received_events) == 1

    def test_unsubscribe_nonexistent_listener(self, event_bus):
        """Test unsubscribing non-existent listener doesn't raise."""

        def listener(event):
            """Stub listener for unsubscribe test - not invoked."""
            del event

        def other_listener(event):
            """Stub listener for unsubscribe test - not invoked."""
            del event

        event_bus.subscribe(TestEvent, listener)
        event_bus.unsubscribe(TestEvent, other_listener)

        # Original listener should still be subscribed
        events = event_bus.subscribed_events
        assert TestEvent in events

    def test_unsubscribe_with_no_registered_event(self, event_bus):
        """Test unsubscribe is a no-op when event has no listeners."""

        def listener(event):
            del event

        event_bus.unsubscribe(TestEvent, listener)
        assert TestEvent not in event_bus.subscribed_events

    def test_unsubscribe_all(self, event_bus):
        """Test unsubscribing all listeners for an event."""

        def listener1(event):
            """Stub listener for unsubscribe_all test - not invoked."""
            del event

        def listener2(event):
            """Stub listener for unsubscribe_all test - not invoked."""
            del event

        event_bus.subscribe(TestEvent, listener1)
        event_bus.subscribe(TestEvent, listener2)
        event_bus.unsubscribe_all(TestEvent)

        events = event_bus.subscribed_events
        assert TestEvent not in events

    @pytest.mark.asyncio
    async def test_emit_notifies_listeners(self, event_bus):
        """Test that emit notifies subscribed listeners."""
        received_events = []

        async def listener(event):
            await asyncio.sleep(0)
            received_events.append(event)

        event_bus.subscribe(AwaitingTestEvent, listener)
        event = AwaitingTestEvent()
        await event_bus.emit(event)

        assert len(received_events) == 1
        assert received_events[0] is event

    @pytest.mark.asyncio
    async def test_emit_notifies_base_event_listener(self, event_bus):
        """Listeners subscribed to a base event receive child event emissions."""
        received_events = []

        async def listener(event):
            await asyncio.sleep(0)
            received_events.append(event)

        event_bus.subscribe(TestEvent, listener)
        event = ChildTestEvent()
        await event_bus.emit(event)

        assert received_events == [event]

    @pytest.mark.asyncio
    async def test_emit_deduplicates_same_listener_across_hierarchy(self, event_bus):
        """A listener registered on base and child should be called once per emit."""
        received_events = []

        async def listener(event):
            await asyncio.sleep(0)
            received_events.append(event)

        event_bus.subscribe(TestEvent, listener)
        event_bus.subscribe(ChildTestEvent, listener)

        event = ChildTestEvent()
        await event_bus.emit(event)

        assert received_events == [event]

    @pytest.mark.asyncio
    async def test_emit_calls_distinct_bound_listeners_from_different_instances(
        self, event_bus
    ):
        """Bound listeners from different instances should each be invoked."""
        owner1 = ListenerOwner()
        owner2 = ListenerOwner()

        event_bus.subscribe(TestEvent, owner1.my_listener)
        event_bus.subscribe(ChildTestEvent, owner2.my_listener)

        event = ChildTestEvent()
        await event_bus.emit(event)

        assert owner1.received_events == [event]
        assert owner2.received_events == [event]

    @pytest.mark.asyncio
    async def test_emit_no_listeners(self, event_bus):
        """Test that emit works with no listeners."""
        event = TestEvent()
        await event_bus.emit(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_emit_awaiting_event(self, event_bus):
        """Test that AWAIT=True events are awaited."""
        call_order = []

        async def listener(evt):
            del evt
            await asyncio.sleep(0)
            call_order.append("listener")

        event_bus.subscribe(AwaitingTestEvent, listener)
        event = AwaitingTestEvent()
        await event_bus.emit(event)
        call_order.append("after_emit")

        # With AWAIT=True, listener should complete before after_emit
        assert call_order == ["listener", "after_emit"]

    @pytest.mark.asyncio
    async def test_emit_non_await_event_creates_background_task(self, event_bus):
        """Test AWAIT=False path schedules listener task and callback handling."""
        received_events = []

        async def listener(event):
            await asyncio.sleep(0)
            received_events.append(event)

        event_bus.subscribe(NonAwaitingTestEvent, listener)
        event = NonAwaitingTestEvent()
        await event_bus.emit(event)

        # Wait a short moment so background task can complete.
        await asyncio.sleep(0.05)

        assert received_events == [event]

    @pytest.mark.asyncio
    async def test_emit_handles_invalid_data_exception(self, event_bus):
        """Test that InvalidDataException in listener is handled gracefully."""

        async def failing_listener(evt):
            del evt
            await asyncio.sleep(0)
            raise InvalidDataException("Test invalid data")

        event_bus.subscribe(AwaitingTestEvent, failing_listener)
        event = AwaitingTestEvent()
        await event_bus.emit(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_emit_raises_stored_critical_error(self):
        bus = EventBus()

        async def failing():
            raise MqttError("boom")

        task = asyncio.create_task(failing())
        await asyncio.gather(task, return_exceptions=True)
        bus._tasks.add(task)
        bus._handle_task_done(task)

        with pytest.raises(MqttError):
            await bus.emit(TestEvent())

        assert bus._critical_error is None

    @pytest.mark.asyncio
    async def test_handle_task_done_logs_second_critical_error(self, monkeypatch):
        bus = EventBus()
        logger_spy = LoggerSpy()
        monkeypatch.setattr("solaredge2mqtt.core.events.logger", logger_spy)

        async def failing(error):
            raise error

        first = asyncio.create_task(failing(MqttError("first")))
        await asyncio.gather(first, return_exceptions=True)
        bus._tasks.add(first)
        bus._handle_task_done(first)

        second = asyncio.create_task(failing(MqttError("second")))
        await asyncio.gather(second, return_exceptions=True)
        bus._tasks.add(second)
        bus._handle_task_done(second)

        assert bus._critical_error is not None
        assert logger_spy.warnings

    @pytest.mark.asyncio
    async def test_handle_task_done_logs_unhandled_error(self, monkeypatch):
        bus = EventBus()
        logger_spy = LoggerSpy()
        monkeypatch.setattr("solaredge2mqtt.core.events.logger", logger_spy)

        async def failing():
            raise ValueError("unexpected")

        task = asyncio.create_task(failing())
        await asyncio.gather(task, return_exceptions=True)
        bus._tasks.add(task)
        bus._handle_task_done(task)

        assert logger_spy.errors

    @pytest.mark.asyncio
    async def test_cancel_tasks(self, event_bus):
        """Test cancel_tasks cancels all pending tasks."""
        await event_bus.cancel_tasks()  # Should not raise on empty tasks

    @pytest.mark.asyncio
    async def test_multiple_listeners_all_called(self, event_bus):
        """Test that multiple listeners are all called."""
        calls = []

        async def listener1(evt):
            del evt
            await asyncio.sleep(0)
            calls.append("listener1")

        async def listener2(evt):
            del evt
            await asyncio.sleep(0)
            calls.append("listener2")

        event_bus.subscribe(AwaitingTestEvent, listener1)
        event_bus.subscribe(AwaitingTestEvent, listener2)
        await event_bus.emit(AwaitingTestEvent())

        assert "listener1" in calls
        assert "listener2" in calls

    def test_unsubscribe_all_for_non_subscribed_event(self, event_bus):
        """Test unsubscribe_all is a no-op for unknown event."""
        event_bus.unsubscribe_all(TestEvent)
        assert TestEvent not in event_bus.subscribed_events

    @pytest.mark.asyncio
    async def test_notify_listeners_raises_mqtt_error(self, event_bus):
        """Test _notify_listeners re-raises critical MQTT listener errors."""

        def mqtt_error_listener(evt):
            del evt
            raise MqttError("critical")

        event_bus.subscribe(AwaitingTestEvent, mqtt_error_listener)

        with pytest.raises(MqttError):
            await event_bus.emit(AwaitingTestEvent())

    @pytest.mark.asyncio
    async def test_notify_listeners_logs_generic_exception(
        self, event_bus, monkeypatch
    ):
        """Test _notify_listeners logs non-critical generic exceptions."""
        logger_spy = LoggerSpy()
        monkeypatch.setattr("solaredge2mqtt.core.events.logger", logger_spy)

        async def generic_error_listener(evt):
            del evt
            await asyncio.sleep(0)
            raise ValueError("generic")

        event_bus.subscribe(AwaitingTestEvent, generic_error_listener)
        await event_bus.emit(AwaitingTestEvent())

        assert logger_spy.errors

    @pytest.mark.asyncio
    async def test_handle_task_done_cancelled_task_returns(self):
        """Test _handle_task_done early return for cancelled tasks."""
        bus = EventBus()

        async def never_finishes():
            await asyncio.sleep(10)

        task = asyncio.create_task(never_finishes())
        bus._tasks.add(task)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        bus._handle_task_done(task)

        assert task not in bus._tasks

    @pytest.mark.asyncio
    async def test_handle_task_done_without_exception_returns(self):
        """Test _handle_task_done early return when task has no exception."""
        bus = EventBus()

        async def success():
            await asyncio.sleep(0)
            return None

        task = asyncio.create_task(success())
        await task
        bus._tasks.add(task)

        bus._handle_task_done(task)

        assert task not in bus._tasks

    @pytest.mark.asyncio
    async def test_cancel_tasks_clears_critical_error(self):
        """Test cancel_tasks resets stored critical error."""
        bus = EventBus()
        bus._critical_error = MqttError("old")

        await bus.cancel_tasks()

        assert bus._critical_error is None

    @pytest.mark.asyncio
    async def test_cancel_tasks_cancels_pending_tasks(self):
        """Test cancel_tasks iterates pending tasks and calls cancel()."""
        bus = EventBus()

        async def sleeper():
            await asyncio.sleep(10)

        task = asyncio.create_task(sleeper())
        bus._tasks.add(task)

        await bus.cancel_tasks()

        assert task.cancelled()
        assert not bus._tasks
