"""Tests for HomeAssistantDiscovery service with mocking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.mqtt.events import (
    MQTTPublishEvent,
    MQTTReceivedEvent,
    MQTTSubscribeEvent,
)
from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.events import ComponentEvent
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.homeassistant import HomeAssistantDiscovery
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType,
    HomeAssistantNumberType,
    HomeAssistantSensorType,
    HomeAssistantStatus,
    HomeAssistantStatusInput,
    HomeAssistantType,
)
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent
from solaredge2mqtt.services.powerflow.events import PowerflowGeneratedEvent


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()

    settings.homeassistant = MagicMock()
    settings.homeassistant.topic_prefix = "homeassistant"
    settings.homeassistant.retain = True

    settings.mqtt = MagicMock()
    settings.mqtt.topic_prefix = "solaredge"
    settings.mqtt.client_id = "test_client"

    settings.modbus = MagicMock()
    settings.modbus.has_followers = False
    settings.modbus.check_grid_status = True
    settings.modbus.advanced_power_controls_enabled = False

    settings.is_prices_configured = False
    settings.prices = MagicMock()
    settings.prices.currency = "EUR"

    return settings


class TestHomeAssistantDiscoveryInit:
    """Tests for HomeAssistantDiscovery initialization."""

    def test_init(self, mock_service_settings, mock_event_bus):
        """Test HomeAssistantDiscovery initialization."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        assert discovery.settings is mock_service_settings
        assert discovery.event_bus is mock_event_bus
        assert discovery._status_topic == "homeassistant/status"

    def test_subscribes_to_events(self, mock_service_settings, mock_event_bus):
        """Test HomeAssistantDiscovery subscribes to events."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        assert mock_event_bus.subscribe.call_count >= 4


class TestHomeAssistantDiscoveryAsyncInit:
    """Tests for HomeAssistantDiscovery async_init."""

    @pytest.mark.asyncio
    async def test_async_init_subscribes_to_status(
        self, mock_service_settings, mock_event_bus
    ):
        """Test async_init subscribes to HA status topic."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        await discovery.async_init()

        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        event = call_args[0][0]
        assert isinstance(event, MQTTSubscribeEvent)
        assert event.topic == "homeassistant/status"


class TestHomeAssistantDiscoveryStateTopic:
    """Tests for HomeAssistantDiscovery state_topic."""

    def test_state_topic_without_name(self, mock_service_settings, mock_event_bus):
        """Test state_topic without name."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        result = discovery.state_topic("powerflow")

        assert result == "solaredge/powerflow"

    def test_state_topic_with_name(self, mock_service_settings, mock_event_bus):
        """Test state_topic with name."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        result = discovery.state_topic("modbus/meter", "meter0")

        assert result == "solaredge/modbus/meter/meter0"


class TestHomeAssistantDiscoveryPropertyParser:
    """Tests for HomeAssistantDiscovery property_parser."""

    def test_property_parser_no_ha_type(self):
        """Test property_parser returns None when no ha_type."""
        result = HomeAssistantDiscovery.property_parser(
            {"name": "test"}, "test", ["test"]
        )

        assert result is None

    def test_property_parser_sensor_type(self):
        """Test property_parser with sensor type."""
        prop = {
            "ha_type": "power_w",
            "ha_typed": "sensor",
            "icon": "mdi:lightning-bolt",
        }

        result = HomeAssistantDiscovery.property_parser(prop, "Power", ["power"])

        assert result is not None
        assert result["name"] == "Power"
        assert result["path"] == ["power"]
        assert result["icon"] == "mdi:lightning-bolt"
        assert isinstance(result["ha_type"], HomeAssistantSensorType)

    def test_property_parser_binary_sensor_type(self):
        """Test property_parser with binary sensor type."""
        prop = {
            "ha_type": "enabled",
            "ha_typed": "binary_sensor",
            "icon": "mdi:power",
        }

        result = HomeAssistantDiscovery.property_parser(prop, "Enabled", ["enabled"])

        assert result is not None
        assert isinstance(result["ha_type"], HomeAssistantBinarySensorType)

    def test_property_parser_number_type(self):
        """Test property_parser with number type."""
        prop = {
            "ha_type": "active_power_limit",
            "ha_typed": "number",
            "icon": "mdi:gauge",
        }

        result = HomeAssistantDiscovery.property_parser(prop, "Limit", ["limit"])

        assert result is not None
        assert isinstance(result["ha_type"], HomeAssistantNumberType)


class TestHomeAssistantDiscoveryComponentDiscovery:
    """Tests for HomeAssistantDiscovery component_discovery."""

    @pytest.mark.asyncio
    async def test_component_discovery_forecast(
        self, mock_service_settings, mock_event_bus
    ):
        """Test component_discovery with forecast event."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)
        discovery.publish_component = AsyncMock()

        mock_component = MagicMock()
        mock_component.mqtt_topic.return_value = "forecast"
        mock_component.homeassistant_device_info.return_value = {}

        event = ForecastEvent(mock_component)

        await discovery.component_discovery(event)

        discovery.publish_component.assert_called_once()
        mock_event_bus.unsubscribe.assert_called()


class TestHomeAssistantDiscoveryUnitsDiscovery:
    """Tests for HomeAssistantDiscovery units_discovery."""

    @pytest.mark.asyncio
    async def test_units_discovery(self, mock_service_settings, mock_event_bus):
        """Test units_discovery with modbus units."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)
        discovery.publish_component = AsyncMock()

        # Create mock inverter
        mock_inverter = MagicMock()
        mock_inverter.mqtt_topic.return_value = "modbus/inverter"
        mock_inverter.homeassistant_device_info.return_value = {}

        # Create mock meter
        mock_meter = MagicMock()
        mock_meter.mqtt_topic.return_value = "modbus/meter"
        mock_meter.homeassistant_device_info_with_name.return_value = {}

        # Create mock unit
        mock_unit = MagicMock()
        mock_unit.inverter = mock_inverter
        mock_unit.meters = {"meter0": mock_meter}
        mock_unit.batteries = {}

        event = ModbusUnitsReadEvent({"leader": mock_unit})

        await discovery.units_discovery(event)

        # Should have published for inverter and meter
        assert discovery.publish_component.call_count == 2


class TestHomeAssistantDiscoveryPowerflowDiscovery:
    """Tests for HomeAssistantDiscovery powerflow_discovery."""

    @pytest.mark.asyncio
    async def test_powerflow_discovery(self, mock_service_settings, mock_event_bus):
        """Test powerflow_discovery."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)
        discovery.publish_component = AsyncMock()

        mock_powerflow = MagicMock()
        mock_powerflow.mqtt_topic.return_value = "powerflow"
        mock_powerflow.homeassistant_device_info.return_value = {}

        event = PowerflowGeneratedEvent({"leader": mock_powerflow})

        await discovery.powerflow_discovery(event)

        discovery.publish_component.assert_called_once()


class TestHomeAssistantDiscoveryStatus:
    """Tests for HomeAssistantDiscovery homeassistant_status."""

    @pytest.mark.asyncio
    async def test_homeassistant_status_online(
        self, mock_service_settings, mock_event_bus
    ):
        """Test handling HA status online event."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        # Add some cached entities
        mock_entity = MagicMock()
        discovery._send_entities["test/topic"] = mock_entity

        # Create mock status input
        mock_input = MagicMock(spec=HomeAssistantStatusInput)
        mock_input.status = HomeAssistantStatus.ONLINE

        event = MQTTReceivedEvent("homeassistant/status", mock_input)

        await discovery.homeassistant_status(event)

        # Should re-emit the cached entity
        mock_event_bus.emit.assert_called()

    @pytest.mark.asyncio
    async def test_homeassistant_status_wrong_topic(
        self, mock_service_settings, mock_event_bus
    ):
        """Test ignoring status events from wrong topic."""
        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        mock_input = MagicMock()
        mock_input.status = HomeAssistantStatus.ONLINE

        event = MQTTReceivedEvent("wrong/topic", mock_input)

        await discovery.homeassistant_status(event)

        # Should not emit anything
        mock_event_bus.emit.assert_not_called()
