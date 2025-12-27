"""Tests for core timer events module."""


from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.timer.events import (
    Interval1MinTriggerEvent,
    Interval5MinTriggerEvent,
    Interval10MinTriggerEvent,
    Interval15MinTriggerEvent,
    IntervalBaseTriggerEvent,
)


class TestTimerEvents:
    """Tests for timer event classes."""

    def test_interval_base_trigger_event_is_base_event(self):
        """Test IntervalBaseTriggerEvent inherits from BaseEvent."""
        assert issubclass(IntervalBaseTriggerEvent, BaseEvent)

    def test_interval_1min_trigger_event_is_base_event(self):
        """Test Interval1MinTriggerEvent inherits from BaseEvent."""
        assert issubclass(Interval1MinTriggerEvent, BaseEvent)

    def test_interval_5min_trigger_event_is_base_event(self):
        """Test Interval5MinTriggerEvent inherits from BaseEvent."""
        assert issubclass(Interval5MinTriggerEvent, BaseEvent)

    def test_interval_10min_trigger_event_is_base_event(self):
        """Test Interval10MinTriggerEvent inherits from BaseEvent."""
        assert issubclass(Interval10MinTriggerEvent, BaseEvent)

    def test_interval_15min_trigger_event_is_base_event(self):
        """Test Interval15MinTriggerEvent inherits from BaseEvent."""
        assert issubclass(Interval15MinTriggerEvent, BaseEvent)

    def test_event_keys_are_unique(self):
        """Test that all timer event keys are unique."""
        event_keys = [
            IntervalBaseTriggerEvent.event_key(),
            Interval1MinTriggerEvent.event_key(),
            Interval5MinTriggerEvent.event_key(),
            Interval10MinTriggerEvent.event_key(),
            Interval15MinTriggerEvent.event_key(),
        ]

        assert len(event_keys) == len(set(event_keys))

    def test_events_can_be_instantiated(self):
        """Test that timer events can be instantiated."""
        events = [
            IntervalBaseTriggerEvent(),
            Interval1MinTriggerEvent(),
            Interval5MinTriggerEvent(),
            Interval10MinTriggerEvent(),
            Interval15MinTriggerEvent(),
        ]

        for event in events:
            assert isinstance(event, BaseEvent)

    def test_timer_events_await_is_false(self):
        """Test that timer events have AWAIT=False (default)."""
        assert IntervalBaseTriggerEvent.AWAIT is False
        assert Interval1MinTriggerEvent.AWAIT is False
        assert Interval5MinTriggerEvent.AWAIT is False
        assert Interval10MinTriggerEvent.AWAIT is False
        assert Interval15MinTriggerEvent.AWAIT is False
