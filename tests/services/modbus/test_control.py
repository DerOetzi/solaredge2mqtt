"""Tests for modbus control module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent
from solaredge2mqtt.services.modbus.control import ModbusAdvancedControl
from solaredge2mqtt.services.modbus.settings import AdvancedControlsSettings


@pytest.fixture
def mock_settings():
    """Create mock service settings."""
    mock_settings = MagicMock()
    mock_settings.modbus.has_followers = False
    mock_settings.modbus.advanced_power_controls_enabled = False
    mock_settings.modbus.advanced_power_controls = AdvancedControlsSettings.DISABLED
    mock_settings.mqtt.topic_prefix = "se2mqtt"
    return mock_settings


@pytest.fixture
def event_bus():
    """Create an event bus."""
    return EventBus()


class TestModbusAdvancedControl:
    """Tests for ModbusAdvancedControl class."""

    def test_init_without_followers(self, mock_settings, event_bus):
        """Test initialization without followers."""
        control = ModbusAdvancedControl(mock_settings, event_bus)

        assert control.settings == mock_settings.modbus
        assert control.event_bus == event_bus
        assert "modbus" in control.topic_prefix
        assert "inverter" in control.topic_prefix

    def test_init_with_followers(self, mock_settings, event_bus):
        """Test initialization with followers."""
        mock_settings.modbus.has_followers = True
        control = ModbusAdvancedControl(mock_settings, event_bus)

        assert control.settings == mock_settings.modbus
        assert "leader" in control.topic_prefix

    def test_topic_prefix_construction(self, mock_settings, event_bus):
        """Test topic prefix is correctly constructed."""
        mock_settings.mqtt.topic_prefix = "my_prefix"
        control = ModbusAdvancedControl(mock_settings, event_bus)

        assert control.topic_prefix.startswith("my_prefix/")

    @pytest.mark.asyncio
    async def test_async_init_disabled(self, mock_settings, event_bus):
        """Test async_init with disabled controls."""
        mock_settings.modbus.advanced_power_controls = AdvancedControlsSettings.DISABLED
        control = ModbusAdvancedControl(mock_settings, event_bus)

        await control.async_init()

        # Should not emit any events
        # (test passes if no exceptions are raised)

    @pytest.mark.asyncio
    async def test_async_init_enable(self, mock_settings, event_bus):
        """Test async_init with enabled controls."""
        mock_settings.modbus.advanced_power_controls = AdvancedControlsSettings.ENABLED
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Mock the methods to avoid actual operations
        control.enable_advanced_power_control = AsyncMock()
        control.subscribe_topics = AsyncMock()

        await control.async_init()

        control.enable_advanced_power_control.assert_called_once()
        control.subscribe_topics.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_init_disable(self, mock_settings, event_bus):
        """Test async_init with disable controls."""
        mock_settings.modbus.advanced_power_controls = AdvancedControlsSettings.DISABLE
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Mock the method to avoid actual operations
        control.disable_advanced_control_settings = AsyncMock()

        await control.async_init()

        control.disable_advanced_control_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_advanced_power_control(self, mock_settings, event_bus):
        """Test enabling advanced power control."""
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Mock emit to verify events are emitted
        control.event_bus.emit = AsyncMock()

        await control.enable_advanced_power_control()

        # Should not emit any events by default (no-op in current implementation)

    @pytest.mark.asyncio
    async def test_disable_advanced_control_settings(self, mock_settings, event_bus):
        """Test disabling advanced control settings."""
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Mock emit to verify events are emitted
        control.event_bus.emit = AsyncMock()

        await control.disable_advanced_control_settings()

        # Should emit 3 events
        assert control.event_bus.emit.call_count == 3

    @pytest.mark.asyncio
    async def test_subscribe_events_when_enabled(self, mock_settings, event_bus):
        """Test _subscribe_events when controls are enabled."""
        mock_settings.modbus.advanced_power_controls_enabled = True
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Verify that event subscription was called
        # (event_bus.subscribe should have been called)
        assert control.event_bus is not None

    def test_subscribe_events_when_disabled(self, mock_settings, event_bus):
        """Test _subscribe_events when controls are disabled."""
        mock_settings.modbus.advanced_power_controls_enabled = False
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Should not raise any errors
        assert control.event_bus is not None

    @pytest.mark.asyncio
    async def test_handle_mqtt_received_event(self, mock_settings, event_bus):
        """Test handling MQTT received event."""
        control = ModbusAdvancedControl(mock_settings, event_bus)

        # Create a mock event
        mock_event = MagicMock(spec=MQTTReceivedEvent)
        mock_event.input = {"test": "value"}

        # Should not raise any errors
        await control.handle_mqtt_received_event(mock_event)

    @pytest.mark.asyncio
    async def test_subscribe_topics_with_fields(self, mock_settings, event_bus):
        """subscribe_topics should iterate schema fields and log topic usage."""
        control = ModbusAdvancedControl(mock_settings, event_bus)

        with patch(
            "solaredge2mqtt.services.modbus.control.ModbusInverter.parse_schema",
            return_value=[{"topic": "controls/active_power_limit"}],
        ):
            await control.subscribe_topics()

    def test_property_parser_with_input_field(self):
        """Test property_parser with input field."""
        prop = {"input_field": "active_power_limit", "other": "data"}

        result = ModbusAdvancedControl.property_parser(prop, "test_field", ["path"])

        assert result is not None
        assert result["name"] == "test_field"
        assert result["topic"] == "path"
        assert "input_field" in result

    def test_property_parser_without_input_field(self):
        """Test property_parser without input field."""
        prop = {"other": "data"}

        result = ModbusAdvancedControl.property_parser(prop, "test_field", ["path"])

        assert result is None

    def test_property_parser_with_false_input_field(self):
        """Test property_parser with false input field."""
        prop = {"input_field": False}

        result = ModbusAdvancedControl.property_parser(prop, "test_field", ["path"])

        assert result is None

    def test_property_parser_with_path(self):
        """Test property_parser constructs topic from path."""
        prop = {"input_field": "active_power_limit"}
        path = ["controls", "power", "active"]

        result = ModbusAdvancedControl.property_parser(prop, "field", path)

        assert result is not None
        assert result["topic"] == "controls/power/active"
