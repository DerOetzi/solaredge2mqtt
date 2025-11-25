"""Tests for core EventBus module."""

import pytest

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.exceptions import InvalidDataException


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
        received = []

        async def listener(event):
            received.append(event)

        event_bus.subscribe(TestEvent, listener)
        listeners = event_bus.subscribed_events
        assert TestEvent in listeners

    def test_subscribe_multiple_events(self, event_bus):
        """Test subscribing to multiple events at once."""
        received = []

        async def listener(event):
            received.append(event)

        class AnotherEvent(BaseEvent):
            """Another test event."""

        event_bus.subscribe([TestEvent, AnotherEvent], listener)
        events = event_bus.subscribed_events
        assert TestEvent in events
        assert AnotherEvent in events

    def test_subscribed_events_property(self, event_bus):
        """Test subscribed_events property returns correct events."""
        received = []

        async def listener(event):
            received.append(event)

        event_bus.subscribe(TestEvent, listener)

        events = event_bus.subscribed_events
        assert TestEvent in events

    def test_unsubscribe(self, event_bus):
        """Test unsubscribing from an event."""
        received = []

        async def listener(event):
            received.append(event)

        event_bus.subscribe(TestEvent, listener)
        event_bus.unsubscribe(TestEvent, listener)

        events = event_bus.subscribed_events
        assert TestEvent not in events

    def test_unsubscribe_nonexistent_listener(self, event_bus):
        """Test unsubscribing non-existent listener doesn't raise."""
        received1 = []
        received2 = []

        async def listener(event):
            received1.append(event)

        async def other_listener(event):
            received2.append(event)

        event_bus.subscribe(TestEvent, listener)
        event_bus.unsubscribe(TestEvent, other_listener)

        # Original listener should still be subscribed
        events = event_bus.subscribed_events
        assert TestEvent in events

    def test_unsubscribe_all(self, event_bus):
        """Test unsubscribing all listeners for an event."""
        received1 = []
        received2 = []

        async def listener1(event):
            received1.append(event)

        async def listener2(event):
            received2.append(event)

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
            _ = evt  # Use the event
            call_order.append("listener")

        event_bus.subscribe(AwaitingTestEvent, listener)
        event = AwaitingTestEvent()
        await event_bus.emit(event)
        call_order.append("after_emit")

        # With AWAIT=True, listener should complete before after_emit
        assert call_order == ["listener", "after_emit"]

    @pytest.mark.asyncio
    async def test_emit_handles_invalid_data_exception(self, event_bus, capfd):
        """Test that InvalidDataException in listener is handled gracefully."""

        async def failing_listener(evt):
            _ = evt  # Use the event
            raise InvalidDataException("Test invalid data")

        event_bus.subscribe(AwaitingTestEvent, failing_listener)
        event = AwaitingTestEvent()
        await event_bus.emit(event)  # Should not raise

    @pytest.mark.asyncio
    async def test_cancel_tasks(self, event_bus):
        """Test cancel_tasks cancels all pending tasks."""
        await event_bus.cancel_tasks()  # Should not raise on empty tasks

    @pytest.mark.asyncio
    async def test_multiple_listeners_all_called(self, event_bus):
        """Test that multiple listeners are all called."""
        calls = []

        async def listener1(evt):
            _ = evt  # Use the event
            calls.append("listener1")

        async def listener2(evt):
            _ = evt  # Use the event
            calls.append("listener2")

        event_bus.subscribe(AwaitingTestEvent, listener1)
        event_bus.subscribe(AwaitingTestEvent, listener2)
        await event_bus.emit(AwaitingTestEvent())

        assert "listener1" in calls
        assert "listener2" in calls
