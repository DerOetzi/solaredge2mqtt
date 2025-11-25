"""Tests for core InfluxDB events module."""


from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent


class TestInfluxDBAggregatedEvent:
    """Tests for InfluxDBAggregatedEvent class."""

    def test_influxdb_aggregated_event_is_base_event(self):
        """Test InfluxDBAggregatedEvent inherits from BaseEvent."""
        assert issubclass(InfluxDBAggregatedEvent, BaseEvent)

    def test_influxdb_aggregated_event_await_is_false(self):
        """Test InfluxDBAggregatedEvent has default AWAIT=False."""
        assert InfluxDBAggregatedEvent.AWAIT is False

    def test_influxdb_aggregated_event_can_be_instantiated(self):
        """Test InfluxDBAggregatedEvent can be instantiated."""
        event = InfluxDBAggregatedEvent()
        assert isinstance(event, BaseEvent)

    def test_influxdb_aggregated_event_key(self):
        """Test InfluxDBAggregatedEvent has correct event key."""
        assert InfluxDBAggregatedEvent.event_key() == "influxdbaggregatedevent"
