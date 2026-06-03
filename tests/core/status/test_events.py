"""Tests for status events."""

from solaredge2mqtt.core.status.events import (
    ServiceOfflineEvent,
    ServiceOnlineEvent,
)


class TestServiceOnlineEvent:
    """Tests for ServiceOnlineEvent."""

    def test_init_with_debounce_cycles(self):
        """Test initialization with debounce_cycles parameter."""
        event = ServiceOnlineEvent(debounce_cycles=5)

        assert event.debounce_cycles == 5

    def test_init_without_debounce_cycles(self):
        """Test initialization without debounce_cycles parameter."""
        event = ServiceOnlineEvent()

        assert event.debounce_cycles is None

    def test_init_with_debounce_cycles_none(self):
        """Test explicit initialization with None for debounce_cycles."""
        event = ServiceOnlineEvent(debounce_cycles=None)

        assert event.debounce_cycles is None

    def test_various_debounce_cycle_values(self):
        """Test with various debounce cycle values."""
        cycles = [0, 1, 5, 10, 100]

        for cycle in cycles:
            event = ServiceOnlineEvent(debounce_cycles=cycle)
            assert event.debounce_cycles == cycle

    def test_event_inheritance(self):
        """Test that ServiceOnlineEvent inherits from BaseEvent."""
        from solaredge2mqtt.core.events.events import BaseEvent

        event = ServiceOnlineEvent(debounce_cycles=5)
        assert isinstance(event, BaseEvent)

    def test_multiple_instances_with_different_values(self):
        """Test creating multiple instances with different values."""
        event1 = ServiceOnlineEvent(debounce_cycles=5)
        event2 = ServiceOnlineEvent(debounce_cycles=10)
        event3 = ServiceOnlineEvent()

        assert event1.debounce_cycles == 5
        assert event2.debounce_cycles == 10
        assert event3.debounce_cycles is None


class TestServiceOfflineEvent:
    """Tests for ServiceOfflineEvent."""

    def test_event_creation(self):
        """Test that ServiceOfflineEvent can be instantiated."""
        event = ServiceOfflineEvent()
        assert isinstance(event, ServiceOfflineEvent)

    def test_event_inheritance(self):
        """Test that ServiceOfflineEvent inherits from BaseEvent."""
        from solaredge2mqtt.core.events.events import BaseEvent

        event = ServiceOfflineEvent()
        assert isinstance(event, BaseEvent)

    def test_multiple_instances_are_independent(self):
        """Test that multiple instances are independent."""
        event1 = ServiceOfflineEvent()
        event2 = ServiceOfflineEvent()

        assert event1 is not event2
