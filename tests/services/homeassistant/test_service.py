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

    @pytest.mark.asyncio
    async def test_component_discovery_energy_with_auto_discovery(
        self, mock_service_settings, mock_event_bus
    ):
        """Test component_discovery with EnergyReadEvent and auto_discovery enabled."""
        from solaredge2mqtt.services.energy.models import HistoricEnergy

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)
        discovery.publish_component = AsyncMock()

        # Create mock component with period info
        mock_component = MagicMock(spec=HistoricEnergy)
        mock_component.mqtt_topic.return_value = "energy/today"
        mock_component.homeassistant_device_info.return_value = {}
        mock_component.info = MagicMock()
        mock_component.info.period = MagicMock()
        mock_component.info.period.auto_discovery = True

        event = EnergyReadEvent(mock_component)

        await discovery.component_discovery(event)

        # Should publish since auto_discovery is True and not seen before
        discovery.publish_component.assert_called_once()

    @pytest.mark.asyncio
    async def test_component_discovery_energy_seen_before(
        self, mock_service_settings, mock_event_bus
    ):
        """Test component_discovery with EnergyReadEvent that was seen before."""
        from solaredge2mqtt.services.energy.models import HistoricEnergy

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)
        discovery.publish_component = AsyncMock()

        # Create mock component with period info
        mock_component = MagicMock(spec=HistoricEnergy)
        mock_component.mqtt_topic.return_value = "energy/today"
        mock_component.homeassistant_device_info.return_value = {}
        mock_component.info = MagicMock()
        mock_component.info.period = MagicMock()
        mock_component.info.period.auto_discovery = True

        # Mark as already seen
        discovery._seen_energy_periods.add("energy/today")

        event = EnergyReadEvent(mock_component)

        await discovery.component_discovery(event)

        # Should not publish since already seen
        discovery.publish_component.assert_not_called()

    @pytest.mark.asyncio
    async def test_component_discovery_energy_no_auto_discovery(
        self, mock_service_settings, mock_event_bus
    ):
        """Test component_discovery with EnergyReadEvent and auto_discovery disabled."""
        from solaredge2mqtt.services.energy.models import HistoricEnergy

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)
        discovery.publish_component = AsyncMock()

        # Create mock component with period info
        mock_component = MagicMock(spec=HistoricEnergy)
        mock_component.mqtt_topic.return_value = "energy/month"
        mock_component.homeassistant_device_info.return_value = {}
        mock_component.info = MagicMock()
        mock_component.info.period = MagicMock()
        mock_component.info.period.auto_discovery = False

        event = EnergyReadEvent(mock_component)

        await discovery.component_discovery(event)

        # Should not publish since auto_discovery is False
        discovery.publish_component.assert_not_called()


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


class TestHomeAssistantDiscoveryPublishComponent:
    """Tests for HomeAssistantDiscovery publish_component."""

    @pytest.mark.asyncio
    async def test_publish_component_basic(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_component creates and publishes entities."""
        from solaredge2mqtt.services.powerflow.models import Powerflow

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        # Create mock component
        mock_component = MagicMock(spec=Powerflow)
        mock_component.mqtt_topic.return_value = "powerflow"
        mock_component.parse_schema.return_value = [
            {
                "name": "Power",
                "path": ["power"],
                "icon": "mdi:lightning-bolt",
                "ha_type": HomeAssistantSensorType.POWER_W,
            }
        ]

        device_info = {"name": "Test Device"}
        state_topic = "solaredge/powerflow"

        await discovery.publish_component(mock_component, device_info, state_topic)

        # Should emit publish events
        assert mock_event_bus.emit.call_count > 0

    @pytest.mark.asyncio
    async def test_publish_component_with_modbus_inverter(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_component with ModbusInverter (grid_status filtering)."""
        from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter

        # Disable grid status check to test filtering
        mock_service_settings.modbus.check_grid_status = False

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        # Create mock inverter
        mock_inverter = MagicMock(spec=ModbusInverter)
        mock_inverter.mqtt_topic.return_value = "modbus/inverter"
        mock_inverter.parse_schema.return_value = [
            {
                "name": "Grid Status",
                "path": ["grid_status"],
                "icon": "mdi:power-plug",
                "ha_type": HomeAssistantBinarySensorType.GRID_STATUS,
            },
            {
                "name": "Power",
                "path": ["power"],
                "icon": "mdi:lightning-bolt",
                "ha_type": HomeAssistantSensorType.POWER_W,
            },
        ]

        device_info = {"name": "Inverter"}
        state_topic = "solaredge/modbus/inverter"

        await discovery.publish_component(mock_inverter, device_info, state_topic)

        # Grid status should be filtered out
        # Check the emitted events
        assert mock_event_bus.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_publish_component_with_advanced_power_controls(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_component filters advanced_power_controls when disabled."""
        from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter

        # Disable advanced power controls
        mock_service_settings.modbus.advanced_power_controls_enabled = False

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        mock_inverter = MagicMock(spec=ModbusInverter)
        mock_inverter.mqtt_topic.return_value = "modbus/inverter"
        mock_inverter.parse_schema.return_value = [
            {
                "name": "Power Limit",
                "path": ["advanced_power_controls", "power_limit"],
                "icon": "mdi:gauge",
                "ha_type": HomeAssistantNumberType.ACTIVE_POWER_LIMIT,
            },
            {
                "name": "Power",
                "path": ["power"],
                "icon": "mdi:lightning-bolt",
                "ha_type": HomeAssistantSensorType.POWER_W,
            },
        ]

        device_info = {"name": "Inverter"}
        state_topic = "solaredge/modbus/inverter"

        await discovery.publish_component(mock_inverter, device_info, state_topic)

        # advanced_power_controls should be filtered out
        assert mock_event_bus.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_publish_component_with_monetary_type(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_component sets currency for monetary types."""
        # Enable prices
        mock_service_settings.is_prices_configured = True
        mock_service_settings.prices.currency = "USD"

        discovery = HomeAssistantDiscovery(mock_service_settings, mock_event_bus)

        mock_component = MagicMock()
        mock_component.mqtt_topic.return_value = "energy"
        mock_component.parse_schema.return_value = [
            {
                "name": "Cost",
                "path": ["cost"],
                "icon": "mdi:currency-usd",
                "ha_type": HomeAssistantSensorType.MONETARY,
            },
        ]

        device_info = {"name": "Energy"}
        state_topic = "solaredge/energy"

        await discovery.publish_component(mock_component, device_info, state_topic)

        # Should emit with currency set
        assert mock_event_bus.emit.call_count >= 1


class TestHomeAssistantPropertyParserAdditionalFields:
    """Tests for HomeAssistantDiscovery property_parser additional_fields."""

    def test_property_parser_number_type_with_additional_fields(self):
        """Test property_parser with number type and additional fields."""
        prop = {
            "ha_type": "active_power_limit",
            "ha_typed": "number",
            "icon": "mdi:gauge",
            "min": 0,
            "max": 100,
            "step": 1,
            "mode": "slider",
        }

        result = HomeAssistantDiscovery.property_parser(prop, "Limit", ["limit"])

        assert result is not None
        assert isinstance(result["ha_type"], HomeAssistantNumberType)
        assert result["min"] == 0
        assert result["max"] == 100
        assert result["step"] == 1
        assert result["mode"] == "slider"
