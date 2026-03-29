"""Tests for homeassistant events module."""

from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.services.homeassistant.events import (
    HomeAssistantStatusEvent,
    HomeAssistantSubscribeEvent,
)
from solaredge2mqtt.services.homeassistant.models import HomeAssistantStatusInput


class TestHomeAssistantStatusEvent:
    """Tests for HomeAssistantStatusEvent class."""

    def test_event_is_mqtt_received_event(self):
        """Test HomeAssistantStatusEvent inherits from MQTTReceivedEvent."""
        assert issubclass(HomeAssistantStatusEvent, MQTTReceivedEvent)

    def test_event_creation(self):
        """Test creating HomeAssistantStatusEvent."""
        status_input = HomeAssistantStatusInput.model_validate("online")
        event = HomeAssistantStatusEvent("test/topic", status_input)

        assert event.input == status_input
        assert event.input.status.status == "online"

    def test_event_with_offline_status(self):
        """Test HomeAssistantStatusEvent with offline status."""
        status_input = HomeAssistantStatusInput.model_validate("offline")
        event = HomeAssistantStatusEvent("test/topic", status_input)

        assert event.input.status.status == "offline"


class TestHomeAssistantSubscribeEvent:
    """Tests for HomeAssistantSubscribeEvent class."""

    def test_event_is_mqtt_subscribe_event(self):
        """Test HomeAssistantSubscribeEvent inherits from MQTTSubscribeEvent."""
        assert issubclass(HomeAssistantSubscribeEvent, MQTTSubscribeEvent)

    def test_event_creation(self):
        """Test creating HomeAssistantSubscribeEvent."""
        subscribe_event = HomeAssistantSubscribeEvent("test/topic")

        assert subscribe_event.topic == "test/topic"
