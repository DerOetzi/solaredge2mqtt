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
        event = MQTTReceivedEvent[TestInput]("test/topic", input_data)

        assert event.topic == "test/topic"
        assert event.input == input_data
        assert event.input.value == pytest.approx(3.14)

    def test_mqtt_received_event_input_model(self):
        """Test input_model returns generic input type."""

        class TestInput(BaseInputField):
            value: int

        class TestReceivedEvent(MQTTReceivedEvent[TestInput]): ...  # pragma: no cover

        assert TestReceivedEvent.input_model() == TestInput

    def test_mqtt_received_event_input_model_raises_type_error(self, monkeypatch):
        """Test input_model raises TypeError when generic type is missing."""

        class InvalidReceivedEvent(MQTTReceivedEvent): ...  # pragma: no cover

        monkeypatch.setattr(InvalidReceivedEvent, "__orig_bases__", ())

        with pytest.raises(
            TypeError,
            match=r"must specify a generic input model",
        ):
            InvalidReceivedEvent.input_model()

    def test_mqtt_received_event_input_model_skips_non_generic_base(self, monkeypatch):
        """Test input_model skips bases without generic args."""

        class TestInput(BaseInputField):
            value: int

        class TestReceivedEvent(MQTTReceivedEvent[TestInput]): ...  # pragma: no cover

        monkeypatch.setattr(
            TestReceivedEvent,
            "__orig_bases__",
            (BaseEvent, MQTTReceivedEvent[TestInput]),
        )

        assert TestReceivedEvent.input_model() is TestInput


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

        class TestReceivedEvent(MQTTReceivedEvent[TestInput]): ...  # pragma: no cover

        class TestSubscribeEvent(
            MQTTSubscribeEvent[TestReceivedEvent]
        ): ...  # pragma: no cover

        event = TestSubscribeEvent("test/topic")

        assert event.topic == "test/topic"
        assert event.event() == TestReceivedEvent

    def test_mqtt_subscribe_event_event_raises_type_error(self, monkeypatch):
        """Test event() raises TypeError when generic type is missing."""

        class InvalidSubscribeEvent(MQTTSubscribeEvent): ...  # pragma: no cover

        monkeypatch.setattr(InvalidSubscribeEvent, "__orig_bases__", ())

        with pytest.raises(
            TypeError,
            match=r"must specify a generic received event",
        ):
            InvalidSubscribeEvent.event()

    def test_mqtt_subscribe_event_event_skips_non_generic_base(self, monkeypatch):
        """Test event() skips bases without generic args."""

        class TestInput(BaseInputField):
            value: float

        class TestReceivedEvent(MQTTReceivedEvent[TestInput]): ...  # pragma: no cover

        class TestSubscribeEvent(
            MQTTSubscribeEvent[TestReceivedEvent]
        ): ...  # pragma: no cover

        monkeypatch.setattr(
            TestSubscribeEvent,
            "__orig_bases__",
            (BaseEvent, MQTTSubscribeEvent[TestReceivedEvent]),
        )

        assert TestSubscribeEvent.event() is TestReceivedEvent
