"""Tests for core MQTTClient module with mocking."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from pydantic import BaseModel

from solaredge2mqtt.core.models import BaseInputField
from solaredge2mqtt.core.mqtt import MQTTClient
from solaredge2mqtt.core.mqtt.events import (
    MQTTPublishEvent,
    MQTTReceivedEvent,
    MQTTSubscribeEvent,
)
from solaredge2mqtt.core.mqtt.settings import MQTTSettings
from solaredge2mqtt.services.homeassistant.events import HomeAssistantStatusEvent


class SampleInputModel(BaseInputField):
    """Test input model for MQTT tests."""

    value: int


class SampleInputEvent(MQTTReceivedEvent[SampleInputModel]): ...  # pragma: no cover


class SampleSubscribeEvent(
    MQTTSubscribeEvent[SampleInputEvent]
): ...  # pragma: no cover


class SamplePayloadModel(BaseModel):
    """Test payload model for MQTT tests."""

    data: str


@pytest.fixture
def mqtt_settings():
    """Create MQTTSettings for testing."""
    return MQTTSettings(
        broker="localhost",
        port=1883,
        topic_prefix="test",
    )


@pytest.fixture
def mock_aiomqtt_client():
    """Create a mock aiomqtt Client."""
    with patch("solaredge2mqtt.core.mqtt.Client.__init__", return_value=None):
        yield


@pytest.fixture
def event_bus():
    """Create an EventBus instance for testing."""
    from solaredge2mqtt.core.events import EventBus

    return EventBus()


@pytest.fixture
def mock_event_bus():
    """Create a mock event bus with mocked emit method."""
    from unittest.mock import AsyncMock, MagicMock

    bus = MagicMock()
    bus.emit = AsyncMock()
    bus.subscribe = MagicMock()
    bus.unsubscribe = MagicMock()
    bus.unsubscribe_all = MagicMock()
    return bus


class TestMQTTClientInit:
    """Tests for MQTTClient initialization."""

    def test_mqtt_client_init(self, mqtt_settings, event_bus, mock_aiomqtt_client):
        """Test MQTTClient initialization."""
        client = MQTTClient(mqtt_settings, event_bus)

        assert client.broker == "localhost"
        assert client.port == 1883
        assert client.topic_prefix == "test"
        assert client.event_bus is event_bus

    def test_mqtt_client_subscribes_to_events(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Test MQTTClient subscribes to MQTT events."""
        client = MQTTClient(mqtt_settings, mock_event_bus)

        # Verify event subscriptions
        mock_event_bus.subscribe.assert_any_call(
            MQTTPublishEvent, client.event_listener
        )
        mock_event_bus.subscribe.assert_any_call(
            MQTTSubscribeEvent, client._subscribe_topic
        )

    @pytest.mark.asyncio
    async def test_context_manager_enter_sets_connected(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test __aenter__ marks client as connected."""
        client = MQTTClient(mqtt_settings, event_bus)

        with patch(
            "solaredge2mqtt.core.mqtt.Client.__aenter__",
            new=AsyncMock(return_value=client),
        ) as mock_enter:
            entered_client = await client.__aenter__()

        assert entered_client is client
        assert client._is_connected is True
        mock_enter.assert_called_once_with()

    @pytest.mark.asyncio
    async def test_context_manager_exit_sets_disconnected(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test __aexit__ marks client as disconnected."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._is_connected = True

        with patch(
            "solaredge2mqtt.core.mqtt.Client.__aexit__",
            new=AsyncMock(return_value=None),
        ) as mock_exit:
            await client.__aexit__(None, None, None)

        assert client._is_connected is False
        mock_exit.assert_called_once_with(None, None, None)


class TestMQTTClientSubscribeTopic:
    """Tests for MQTTClient topic subscription."""

    @pytest.mark.asyncio
    async def test_subscribe_topic_new_topic(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test subscribing to a new topic."""
        client = MQTTClient(mqtt_settings, event_bus)
        client.subscribe = AsyncMock()

        event = SampleSubscribeEvent("test/topic")
        await client._subscribe_topic(event)

        assert "test/topic" in client._subscribed_topics
        print(client._subscribed_topics)
        assert client._subscribed_topics["test/topic"] == SampleInputEvent
        client.subscribe.assert_called_once_with("test/topic")

    @pytest.mark.asyncio
    async def test_subscribe_topic_existing_topic(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test subscribing to an already subscribed topic does nothing."""
        client = MQTTClient(mqtt_settings, event_bus)
        client.subscribe = AsyncMock()
        client._subscribed_topics["test/topic"] = SampleInputEvent

        event = SampleSubscribeEvent("test/topic")
        await client._subscribe_topic(event)

        # Should not subscribe again
        client.subscribe.assert_not_called()


class TestMQTTClientHandleMessage:
    """Tests for MQTTClient message handling."""

    @pytest.mark.asyncio
    async def test_handle_message_valid_dict(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Test handling a valid message with dict payload."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        # Create mock message
        mock_message = MagicMock()
        mock_message.topic = MagicMock()
        mock_message.topic.__str__ = MagicMock(return_value="test/topic")
        mock_message.payload = b'{"value": 42}'

        await client._handle_message(mock_message)

        # Verify event was emitted
        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        event = call_args[0][0]
        assert isinstance(event, MQTTReceivedEvent)
        assert event.topic == "test/topic"
        assert event.input.value == 42

    @pytest.mark.asyncio
    async def test_handle_message_valid_string(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Test handling a valid message with string payload that becomes JSON."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        # The handler tries to parse as JSON then as dict/scalar
        mock_message = MagicMock()
        mock_message.topic = MagicMock()
        mock_message.topic.__str__ = MagicMock(return_value="test/topic")
        mock_message.payload = b'{"value": 99}'

        await client._handle_message(mock_message)

        # Verify event was emitted
        mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", ["online", "offline"])
    async def test_handle_message_homeassistant_status_scalar_payload(
        self,
        payload,
        mqtt_settings,
        mock_event_bus,
        mock_aiomqtt_client,
    ):
        """Test handling Home Assistant online/offline scalar payload."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["homeassistant/status"] = HomeAssistantStatusEvent

        mock_message = MagicMock()
        mock_message.topic = MagicMock()
        mock_message.topic.__str__ = MagicMock(return_value="homeassistant/status")
        mock_message.payload = f'"{payload}"'.encode()

        await client._handle_message(mock_message)

        mock_event_bus.emit.assert_called_once()
        emitted_event = mock_event_bus.emit.call_args[0][0]
        assert isinstance(emitted_event, HomeAssistantStatusEvent)
        assert emitted_event.topic == "homeassistant/status"
        assert emitted_event.input.status.status == payload

    @pytest.mark.asyncio
    async def test_handle_message_unexpected_topic(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Test handling message for unexpected topic."""
        client = MQTTClient(mqtt_settings, mock_event_bus)

        mock_message = MagicMock()
        mock_message.topic = MagicMock()
        mock_message.topic.__str__ = MagicMock(return_value="unknown/topic")
        mock_message.payload = b'{"value": 42}'

        await client._handle_message(mock_message)

        # Should not emit any event
        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_invalid_json(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Test handling message with invalid JSON."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        mock_message = MagicMock()
        mock_message.topic = MagicMock()
        mock_message.topic.__str__ = MagicMock(return_value="test/topic")
        mock_message.payload = b"not valid json {{"

        # Should not raise, just log warning
        await client._handle_message(mock_message)
        mock_event_bus.emit.assert_not_called()


class TestMQTTClientPublish:
    """Tests for MQTTClient publish methods."""

    @pytest.mark.asyncio
    async def test_publish_status_online(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test publishing online status."""
        client = MQTTClient(mqtt_settings, event_bus)
        client.publish_to = AsyncMock()

        await client.publish_status_online()

        client.publish_to.assert_called_once_with("status", "online", True)

    @pytest.mark.asyncio
    async def test_publish_status_offline(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test publishing offline status."""
        client = MQTTClient(mqtt_settings, event_bus)
        client.publish_to = AsyncMock()

        await client.publish_status_offline()

        client.publish_to.assert_called_once_with("status", "offline", True)

    @pytest.mark.asyncio
    async def test_event_listener(self, mqtt_settings, event_bus, mock_aiomqtt_client):
        """Test event listener calls publish_to."""
        client = MQTTClient(mqtt_settings, event_bus)
        client.publish_to = AsyncMock()

        event = MQTTPublishEvent(
            "test/topic",
            "payload",
            True,
            qos=1,
            topic_prefix="custom",
            exclude_none=True,
        )
        await client.event_listener(event)

        client.publish_to.assert_called_once_with(
            "test/topic",
            "payload",
            True,
            1,
            "custom",
            True,
        )

    @pytest.mark.asyncio
    async def test_publish_to_string_payload(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test publish_to with string payload."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._is_connected = True
        client.publish = AsyncMock()

        await client.publish_to("topic", "payload", True, qos=1)

        client.publish.assert_called_once()
        call_args = client.publish.call_args
        assert call_args[0][0] == "test/topic"
        assert call_args[0][1] == "payload"
        assert call_args[1]["qos"] == 1
        assert call_args[1]["retain"] is True

    @pytest.mark.asyncio
    async def test_publish_to_model_payload(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test publish_to with BaseModel payload."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._is_connected = True
        client.publish = AsyncMock()

        payload = SamplePayloadModel(data="test")
        await client.publish_to("topic", payload, False, qos=0)

        client.publish.assert_called_once()
        call_args = client.publish.call_args
        assert call_args[0][0] == "test/topic"
        # Payload should be JSON string
        assert isinstance(call_args[0][1], str)
        assert "test" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_publish_to_custom_prefix(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test publish_to with custom topic prefix."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._is_connected = True
        client.publish = AsyncMock()

        await client.publish_to("topic", "payload", True, topic_prefix="custom")

        client.publish.assert_called_once()
        call_args = client.publish.call_args
        assert call_args[0][0] == "custom/topic"

    @pytest.mark.asyncio
    async def test_publish_to_not_connected(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test publish_to when not connected does nothing."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._is_connected = False
        client.publish = AsyncMock()

        await client.publish_to("topic", "payload", True, topic_prefix="test")

        client.publish.assert_not_called()


class TestMQTTClientListen:
    """Tests for MQTTClient listen method."""

    @pytest.mark.asyncio
    async def test_listen_no_subscriptions(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test listen returns immediately with no subscriptions."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._subscribed_topics = {}

        # Should return immediately without blocking
        await client.listen()

    @pytest.mark.asyncio
    async def test_listen_ignores_unsubscribed_topic(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Skip messages received on topics that are not subscribed."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._subscribed_topics = {"test/topic": SampleInputEvent}

        msg = MagicMock()
        msg.topic = "other/topic"
        msg.payload = b'{"value": 1}'

        async def message_stream():
            yield msg

        with patch.object(
            MQTTClient,
            "messages",
            new_callable=PropertyMock,
            return_value=message_stream(),
        ):
            await client.listen()

        assert client._received_message_queue.empty()

    @pytest.mark.asyncio
    async def test_listen_ignores_large_payload(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Skip messages that exceed maximum payload size."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._subscribed_topics = {"test/topic": SampleInputEvent}

        msg = MagicMock()
        msg.topic = "test/topic"
        msg.payload = b"x" * 60000

        async def message_stream():
            yield msg

        with patch.object(
            MQTTClient,
            "messages",
            new_callable=PropertyMock,
            return_value=message_stream(),
        ):
            await client.listen()

        assert client._received_message_queue.empty()

    @pytest.mark.asyncio
    async def test_listen_drops_message_when_queue_full(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Drop messages when processing queue is full."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._subscribed_topics = {"test/topic": SampleInputEvent}
        client._received_message_queue = asyncio.Queue(maxsize=1)

        first = MagicMock()
        first.topic = "test/topic"
        first.payload = b'{"value": 1}'
        second = MagicMock()
        second.topic = "test/topic"
        second.payload = b'{"value": 2}'

        async def message_stream():
            yield first
            yield second

        with patch.object(
            MQTTClient,
            "messages",
            new_callable=PropertyMock,
            return_value=message_stream(),
        ):
            await client.listen()

        assert client._received_message_queue.qsize() == 1


class TestMQTTClientProcessQueue:
    """Tests for MQTTClient process_queue method."""

    @pytest.mark.asyncio
    async def test_process_queue_no_subscriptions(
        self, mqtt_settings, event_bus, mock_aiomqtt_client
    ):
        """Test process_queue returns immediately with no subscriptions."""
        client = MQTTClient(mqtt_settings, event_bus)
        client._subscribed_topics = {}

        # Should return immediately without blocking
        await client.process_queue()

    @pytest.mark.asyncio
    async def test_process_queue_handles_exception(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Test process_queue handles exceptions in message handling."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        # Add a message to the queue
        mock_message = MagicMock()
        mock_message.topic = MagicMock()
        mock_message.topic.__str__ = MagicMock(return_value="test/topic")
        mock_message.payload = b'{"value": 42}'
        await client._received_message_queue.put(mock_message)

        # Mock _handle_message to raise an exception
        client._handle_message = AsyncMock(side_effect=Exception("Test error"))

        # Run process_queue in background task
        task = asyncio.create_task(client.process_queue())
        await asyncio.sleep(0.1)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Should have attempted to handle the message
        client._handle_message.assert_called_once()


class TestMQTTClientHandleMessageErrors:
    """Additional error-path tests for _handle_message."""

    @pytest.mark.asyncio
    async def test_handle_message_invalid_payload_type_logs_warning(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Invalid payload type should not emit events."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        mock_message = MagicMock()
        mock_message.topic = "test/topic"
        mock_message.payload = b'"string-not-accepted"'

        await client._handle_message(mock_message)

        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_validation_error_is_caught(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """Validation errors are handled without raising."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        mock_message = MagicMock()
        mock_message.topic = "test/topic"
        mock_message.payload = b'{"value":"not-an-int"}'

        await client._handle_message(mock_message)

        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_null_payload_is_rejected(
        self, mqtt_settings, mock_event_bus, mock_aiomqtt_client
    ):
        """JSON null payload should be rejected as invalid input type."""
        client = MQTTClient(mqtt_settings, mock_event_bus)
        client._subscribed_topics["test/topic"] = SampleInputEvent

        mock_message = MagicMock()
        mock_message.topic = "test/topic"
        mock_message.payload = b"null"

        await client._handle_message(mock_message)

        mock_event_bus.emit.assert_not_called()
