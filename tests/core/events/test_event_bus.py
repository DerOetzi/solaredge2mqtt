"""Tests for core EventBus module."""

import asyncio

import pytest
from aiomqtt import MqttError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.exceptions import InvalidDataException


class LoggerSpy:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def warning(self, message, **kwargs):
        self.warnings.append((message, kwargs))

    def error(self, message, **kwargs):
        self.errors.append((message, kwargs))


class TestEvent(BaseEvent):
    """Test event class."""


class AwaitingTestEvent(BaseEvent):
    """Test event with AWAIT=True."""

    AWAIT = True


class TestEventBus:
    """Tests for EventBus class."""

    def test_event_bus_initialization(self):
        """Test EventBus initializes with empty listeners."""
        bus = EventBus()
        events = bus.subscribed_events
        assert len(events) == 0

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
    async def test_handle_task_done_logs_second_critical_error(
        self, monkeypatch
    ):
        bus = EventBus()
        logger_spy = LoggerSpy()
        monkeypatch.setattr(
            "solaredge2mqtt.core.events.logger", logger_spy
        )

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
    async def test_handle_task_done_logs_unhandled_error(
        self, monkeypatch
    ):
        bus = EventBus()
        logger_spy = LoggerSpy()
        monkeypatch.setattr(
            "solaredge2mqtt.core.events.logger", logger_spy
        )

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
