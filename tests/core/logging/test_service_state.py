"""Tests for ServiceStateMixin."""

import pytest

from solaredge2mqtt.core.logging.models import ServiceStateEnum
from solaredge2mqtt.core.logging.service_state import ServiceStateMixin
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent


class _ExampleService(ServiceStateMixin):
    SERVICE_STATE_NAME = "test_service"

    def __init__(self, event_bus=None):
        self._init_service_state()
        self.event_bus = event_bus


class TestServiceStateMixin:
    """Tests for ServiceStateMixin base class."""

    def test_initial_state_is_unknown(self):
        """State should be UNKNOWN right after _init_service_state()."""
        svc = _ExampleService()
        assert svc.service_state == ServiceStateEnum.UNKNOWN

    @pytest.mark.asyncio
    async def test_set_service_state_emits_mqtt_event(self, mock_event_bus):
        """Changing state should emit an MQTTPublishEvent."""
        svc = _ExampleService(event_bus=mock_event_bus)

        await svc._set_service_state(ServiceStateEnum.CONNECTED, mock_event_bus)

        mock_event_bus.emit.assert_awaited_once()
        event: MQTTPublishEvent = mock_event_bus.emit.call_args[0][0]
        assert isinstance(event, MQTTPublishEvent)
        assert event.topic == "status/test_service"
        assert event.payload == ServiceStateEnum.CONNECTED.value
        assert event.retain is True

    @pytest.mark.asyncio
    async def test_set_service_state_no_duplicate_emit(self, mock_event_bus):
        """Same state set twice should not emit a second event."""
        svc = _ExampleService(event_bus=mock_event_bus)

        await svc._set_service_state(ServiceStateEnum.CONNECTED, mock_event_bus)
        await svc._set_service_state(ServiceStateEnum.CONNECTED, mock_event_bus)

        assert mock_event_bus.emit.await_count == 1

    @pytest.mark.asyncio
    async def test_set_service_state_transitions(self, mock_event_bus):
        """State transitions should each emit a separate event."""
        svc = _ExampleService(event_bus=mock_event_bus)

        await svc._set_service_state(ServiceStateEnum.CONNECTED, mock_event_bus)
        await svc._set_service_state(ServiceStateEnum.ERROR, mock_event_bus)

        assert mock_event_bus.emit.await_count == 2
        assert svc.service_state == ServiceStateEnum.ERROR

    @pytest.mark.asyncio
    async def test_state_updates_after_transition(self, mock_event_bus):
        """service_state property should reflect the most recent state."""
        svc = _ExampleService(event_bus=mock_event_bus)

        assert svc.service_state == ServiceStateEnum.UNKNOWN
        await svc._set_service_state(ServiceStateEnum.DISCONNECTED, mock_event_bus)
        assert svc.service_state == ServiceStateEnum.DISCONNECTED
