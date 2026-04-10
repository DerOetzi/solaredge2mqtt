"""Tests for powerflow events module."""

from solaredge2mqtt.services.powerflow.events import PowerflowGeneratedEvent


class TestPowerflowGeneratedEvent:
    """Tests for PowerflowGeneratedEvent class."""

    def test_event_creation(self):
        """Test creating PowerflowGeneratedEvent."""
        # PowerflowGeneratedEvent inherits from ComponentsEvent
        # which requires a dict keyed by component id
        event = PowerflowGeneratedEvent({})

        assert event.components == {}

    def test_event_with_empty_components(self):
        """Test PowerflowGeneratedEvent with empty components dict."""
        event = PowerflowGeneratedEvent({})

        assert isinstance(event.components, dict)
        assert len(event.components) == 0
