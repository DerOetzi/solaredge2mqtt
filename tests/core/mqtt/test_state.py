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
        assert event.retain is False
        assert event.suppress_connection_error is True

    @pytest.mark.asyncio
    async def test_state_change_without_debounce_emits_immediately(
        self, mock_event_bus
    ):
        controller = ServiceStateController("modbus")

        await controller.set_online()
        await controller.set_offline()

        assert mock_event_bus.emit.call_count == 2
        event = mock_event_bus.emit.call_args.args[0]
        assert isinstance(event, MQTTPublishEvent)
        assert event.topic == "status/modbus"
        assert event.payload == "offline"
        assert event.retain is False
        assert event.suppress_connection_error is True

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

    @pytest.mark.asyncio
    async def test_state_change_debounce_increments_count(self, mock_event_bus):
        """Debounce should increment pending count when state matches."""
        controller = ServiceStateController("modbus", debounce_cycles=3)

        await controller.set_online()
        assert mock_event_bus.emit.call_count == 1

        await controller.set_offline()  # First change
        await controller.set_offline()  # Second matching change (increment count)
        assert mock_event_bus.emit.call_count == 1  # Not yet published

        await controller.set_offline()  # Third matching change (reach threshold)
        assert mock_event_bus.emit.call_count == 2  # Now published
        event = mock_event_bus.emit.call_args.args[0]
        assert event.payload == "offline"

    @pytest.mark.asyncio
    async def test_state_change_resets_pending_on_different_state(self, mock_event_bus):
        """Debounce should reset pending state on different state."""
        controller = ServiceStateController("modbus", debounce_cycles=3)

        await controller.set_online()
        await controller.set_offline()  # Start pending transition
        await controller.set_online()   # Different state, resets pending
        await controller.set_online()   # Same as first, should emit immediately
        await controller.set_online()

        assert mock_event_bus.emit.call_count == 1
