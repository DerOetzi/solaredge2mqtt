"""Tests for core MQTT events module."""

import pytest
from pydantic import BaseModel

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.models import BaseInputField
from solaredge2mqtt.core.mqtt.events import (
    MQTTPublishEvent,
    MQTTReceivedEvent,
    MQTTSubscribeEvent,
)


class TestMQTTPublishEvent:
    """Tests for MQTTPublishEvent class."""

    def test_mqtt_publish_event_is_base_event(self):
        """Test MQTTPublishEvent inherits from BaseEvent."""
        assert issubclass(MQTTPublishEvent, BaseEvent)

    def test_mqtt_publish_event_await_is_true(self):
        """Test MQTTPublishEvent has AWAIT=True."""
        assert MQTTPublishEvent.AWAIT is True

    def test_mqtt_publish_event_basic(self):
        """Test MQTTPublishEvent with basic parameters."""
        event = MQTTPublishEvent("test/topic", "payload", True)

        assert event.topic == "test/topic"
        assert event.payload == "payload"
        assert event.retain is True
        assert event.qos == 0
        assert event.topic_prefix is None
        assert event.exclude_none is False

    def test_mqtt_publish_event_all_params(self):
        """Test MQTTPublishEvent with all parameters."""
        event = MQTTPublishEvent(
            "test/topic",
            "payload",
            False,
            qos=1,
            topic_prefix="custom",
            exclude_none=True,
        )

        assert event.topic == "test/topic"
        assert event.payload == "payload"
        assert event.retain is False
        assert event.qos == 1
        assert event.topic_prefix == "custom"
        assert event.exclude_none is True

    def test_mqtt_publish_event_numeric_payload(self):
        """Test MQTTPublishEvent with numeric payload."""
        event_int = MQTTPublishEvent("topic", 42, True)
        event_float = MQTTPublishEvent("topic", 3.14, True)

        assert event_int.payload == 42
        assert event_float.payload == pytest.approx(3.14)

    def test_mqtt_publish_event_model_payload(self):
        """Test MQTTPublishEvent with BaseModel payload."""

        class TestPayload(BaseModel):
            value: int

        payload = TestPayload(value=100)
        event = MQTTPublishEvent("topic", payload, True)

        assert event.payload == payload
        assert isinstance(event.payload, BaseModel)


class TestMQTTReceivedEvent:
    """Tests for MQTTReceivedEvent class."""

    def test_mqtt_received_event_is_base_event(self):
        """Test MQTTReceivedEvent inherits from BaseEvent."""
        assert issubclass(MQTTReceivedEvent, BaseEvent)

    def test_mqtt_received_event_await_is_false(self):
        """Test MQTTReceivedEvent has default AWAIT=False."""
        assert MQTTReceivedEvent.AWAIT is False

    def test_mqtt_received_event_properties(self):
        """Test MQTTReceivedEvent stores topic and input."""

        class TestInput(BaseInputField):
            value: float

        input_data = TestInput(value=3.14)
        event = MQTTReceivedEvent("test/topic", input_data)

        assert event.topic == "test/topic"
        assert event.input == input_data
        assert event.input.value == pytest.approx(3.14)


class TestMQTTSubscribeEvent:
    """Tests for MQTTSubscribeEvent class."""

    def test_mqtt_subscribe_event_is_base_event(self):
        """Test MQTTSubscribeEvent inherits from BaseEvent."""
        assert issubclass(MQTTSubscribeEvent, BaseEvent)

    def test_mqtt_subscribe_event_await_is_true(self):
        """Test MQTTSubscribeEvent has AWAIT=True."""
        assert MQTTSubscribeEvent.AWAIT is True

    def test_mqtt_subscribe_event_properties(self):
        """Test MQTTSubscribeEvent stores topic and model."""

        class TestInput(BaseInputField):
            value: float

        event = MQTTSubscribeEvent("test/topic", TestInput)

        assert event.topic == "test/topic"
        assert event.model == TestInput
