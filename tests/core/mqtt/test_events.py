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
        assert TestReceivedEvent._model_type is TestInput

    def test_mqtt_received_event_init_subclass_raises_without_generic(self):
        """Test __init_subclass__ raises TypeError when generic type is missing."""

        with pytest.raises(
            TypeError,
            match=r"must specify a generic input model",
        ):

            class InvalidReceivedEvent(MQTTReceivedEvent):  # noqa: S5603
                ...  # pragma: no cover

    def test_mqtt_received_event_init_subclass_skips_non_matching_origin(
        self, monkeypatch
    ):
        """Test __init_subclass__ continues when origin is not MQTTReceivedEvent."""

        class TestInput(BaseInputField):
            value: int

        import solaredge2mqtt.core.mqtt.events as mqtt_events

        monkeypatch.setattr(mqtt_events, "get_origin", lambda _base: BaseEvent)

        with pytest.raises(
            TypeError,
            match=r"must specify a generic input model",
        ):

            class InvalidReceivedEvent(  # noqa: S5603
                MQTTReceivedEvent[TestInput]
            ): ...

    def test_mqtt_received_event_init_subclass_raises_when_generic_args_empty(
        self, monkeypatch
    ):
        """Test __init_subclass__ raises when matching origin has empty args."""

        class TestInput(BaseInputField):
            value: int

        import solaredge2mqtt.core.mqtt.events as mqtt_events

        monkeypatch.setattr(
            mqtt_events,
            "get_origin",
            lambda _base: MQTTReceivedEvent,
        )
        monkeypatch.setattr(mqtt_events, "get_args", lambda _base: ())

        with pytest.raises(
            TypeError,
            match=r"must specify a generic input model",
        ):

            class InvalidReceivedEvent(  # noqa: S5603
                MQTTReceivedEvent[TestInput]
            ): ...


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
        assert TestSubscribeEvent._event_type is TestReceivedEvent

    def test_mqtt_subscribe_event_init_subclass_raises_without_generic(self):
        """Test __init_subclass__ raises TypeError when generic type is missing."""

        with pytest.raises(
            TypeError,
            match=r"must specify a generic received event",
        ):

            class InvalidSubscribeEvent(MQTTSubscribeEvent):  # noqa: S5603
                ...  # noqa: S5603

    def test_mqtt_subscribe_event_init_subclass_skips_non_matching_origin(
        self, monkeypatch
    ):
        """Test __init_subclass__ continues when origin is not MQTTSubscribeEvent."""

        class TestInput(BaseInputField):
            value: float

        class TestReceivedEvent(MQTTReceivedEvent[TestInput]): ...  # pragma: no cover

        import solaredge2mqtt.core.mqtt.events as mqtt_events

        monkeypatch.setattr(mqtt_events, "get_origin", lambda _base: BaseEvent)

        with pytest.raises(
            TypeError,
            match=r"must specify a generic received event",
        ):

            class InvalidSubscribeEvent(  # noqa: S5603
                MQTTSubscribeEvent[TestReceivedEvent]
            ): ...

    def test_mqtt_subscribe_event_init_subclass_raises_when_generic_args_empty(
        self, monkeypatch
    ):
        """Test __init_subclass__ raises when matching origin has empty args."""

        class TestInput(BaseInputField):
            value: float

        class TestReceivedEvent(MQTTReceivedEvent[TestInput]): ...  # pragma: no cover

        import solaredge2mqtt.core.mqtt.events as mqtt_events

        monkeypatch.setattr(
            mqtt_events,
            "get_origin",
            lambda _base: MQTTSubscribeEvent,
        )
        monkeypatch.setattr(mqtt_events, "get_args", lambda _base: ())

        with pytest.raises(
            TypeError,
            match=r"must specify a generic received event",
        ):

            class InvalidSubscribeEvent(  # noqa: S5603
                MQTTSubscribeEvent[TestReceivedEvent]
            ): ...
