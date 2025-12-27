"""Tests for core events module."""


from solaredge2mqtt.core.events.events import BaseEvent


class TestBaseEvent:
    """Tests for BaseEvent class."""

    def test_base_event_await_default(self):
        """Test that BaseEvent has AWAIT set to False by default."""
        assert BaseEvent.AWAIT is False

    def test_base_event_event_key(self):
        """Test that event_key returns lowercase class name."""
        assert BaseEvent.event_key() == "baseevent"

    def test_custom_event_event_key(self):
        """Test that custom events return correct event_key."""

        class CustomTestEvent(BaseEvent):
            pass

        assert CustomTestEvent.event_key() == "customtestevent"

    def test_custom_event_with_await(self):
        """Test that custom events can override AWAIT."""

        class AwaitingEvent(BaseEvent):
            AWAIT = True

        assert AwaitingEvent.AWAIT is True

    def test_event_key_case_insensitive(self):
        """Test that event_key is always lowercase."""

        class MyCustomTestEventWithLongName(BaseEvent):
            pass

        expected = "mycustomtesteventwithlong name".replace(" ", "")
        assert MyCustomTestEventWithLongName.event_key() == expected
