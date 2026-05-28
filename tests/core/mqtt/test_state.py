"""Tests for MQTT service state controller."""

import pytest

from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.mqtt.state import ServiceStateController


class TestServiceStateController:
    @pytest.mark.asyncio
    async def test_set_online_emits_state(self, mock_event_bus):
        controller = ServiceStateController("modbus")

        await controller.set_online()

        mock_event_bus.emit.assert_called_once()
        event = mock_event_bus.emit.call_args.args[0]
        assert isinstance(event, MQTTPublishEvent)
        assert event.topic == "status/modbus"
        assert event.payload == "online"
        assert event.retain is True

    @pytest.mark.asyncio
    async def test_same_state_is_not_emitted_twice(self, mock_event_bus):
        controller = ServiceStateController("modbus")

        await controller.set_online()
        await controller.set_online()

        mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_state_change_is_debounced_until_threshold(self, mock_event_bus):
        controller = ServiceStateController("modbus", debounce_cycles=2)

        await controller.set_online()
        await controller.set_offline()

        assert mock_event_bus.emit.call_count == 1

        await controller.set_offline()

        assert mock_event_bus.emit.call_count == 2
        event = mock_event_bus.emit.call_args.args[0]
        assert isinstance(event, MQTTPublishEvent)
        assert event.payload == "offline"
