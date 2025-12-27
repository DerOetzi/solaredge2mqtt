"""Tests for PowerflowService with mocking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.powerflow import PowerflowService
from solaredge2mqtt.services.powerflow.events import PowerflowGeneratedEvent
from solaredge2mqtt.services.powerflow.models import (
    BatteryPowerflow,
    ConsumerPowerflow,
    GridPowerflow,
    InverterPowerflow,
    Powerflow,
)


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()
    settings.modbus = MagicMock()
    settings.modbus.host = "localhost"
    settings.modbus.port = 1502
    settings.modbus.timeout = 5
    settings.modbus.has_followers = False
    settings.modbus.retain = False
    settings.modbus.units = {"leader": MagicMock()}

    settings.powerflow = MagicMock()
    settings.powerflow.retain = False
    settings.powerflow.external_production = 0

    settings.wallbox = MagicMock()
    settings.wallbox.retain = False
    settings.is_wallbox_configured = False

    settings.location = MagicMock()
    settings.location.latitude = 52.52
    settings.location.longitude = 13.405

    return settings


@pytest.fixture
def mock_influxdb():
    """Create mock InfluxDB client."""
    influxdb = AsyncMock()
    influxdb.write_points = AsyncMock()
    return influxdb


@pytest.fixture
def mock_modbus_unit():
    """Create mock ModbusUnit."""
    # Create mock device info
    mock_info = MagicMock()
    mock_info.unit_key.return_value = "leader:"
    mock_info.manufacturer = "SolarEdge"
    mock_info.model = "SE10K"
    mock_info.serialnumber = "12345"
    mock_info.unit = MagicMock()
    mock_info.unit.key = "leader"

    # Create mock inverter
    mock_inverter = MagicMock()
    mock_inverter.info = mock_info
    mock_inverter.ac.power.actual = 1000
    mock_inverter.dc.power = 1200
    mock_inverter.energytotal = 50000
    mock_inverter.grid_status = "ON"
    mock_inverter.status = "ON"
    mock_inverter.mqtt_topic.return_value = "modbus/inverter"
    mock_inverter.is_valid = True

    # Create mock battery
    mock_battery = MagicMock()
    mock_battery.info = mock_info
    mock_battery.power = 0
    mock_battery.state_of_charge = 80
    mock_battery.status = "ON"
    mock_battery.mqtt_topic.return_value = "modbus/battery"
    mock_battery.is_valid = True
    mock_battery.prepare_point.return_value = MagicMock()

    # Create mock meter
    mock_meter = MagicMock()
    mock_meter.info = mock_info
    mock_meter.info.option = "Export+Import"
    mock_meter.power.actual = 500
    mock_meter.energy.totalimport = 10000
    mock_meter.energy.totalexport = 5000
    mock_meter.mqtt_topic.return_value = "modbus/meter"

    # Create mock unit
    mock_unit = MagicMock()
    mock_unit.info = mock_info.unit
    mock_unit.inverter = mock_inverter
    mock_unit.meters = {"meter0": mock_meter}
    mock_unit.batteries = {"battery0": mock_battery}

    return mock_unit


class TestPowerflowServiceInit:
    """Tests for PowerflowService initialization."""

    def test_powerflow_service_init(self, mock_service_settings, mock_event_bus):
        """Test PowerflowService initialization."""
        with patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus:
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            assert service.settings is mock_service_settings
            assert service.event_bus is mock_event_bus
            assert service.influxdb is None
            assert service.wallbox is None

    def test_powerflow_service_init_with_wallbox(
        self, mock_service_settings, mock_event_bus
    ):
        """Test PowerflowService initialization with wallbox."""
        mock_service_settings.is_wallbox_configured = True

        with patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus, patch(
            "solaredge2mqtt.services.powerflow.WallboxClient"
        ) as mock_wallbox:
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            assert service.wallbox is not None

    def test_powerflow_service_init_with_influxdb(
        self, mock_service_settings, mock_event_bus, mock_influxdb
    ):
        """Test PowerflowService initialization with InfluxDB."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, mock_influxdb
            )

            assert service.influxdb is mock_influxdb


class TestPowerflowServiceAsyncInit:
    """Tests for PowerflowService async_init."""

    @pytest.mark.asyncio
    async def test_async_init(self, mock_service_settings, mock_event_bus):
        """Test async_init initializes modbus."""
        with patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class:
            mock_modbus = AsyncMock()
            mock_modbus_class.return_value = mock_modbus

            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )
            await service.async_init()

            mock_modbus.async_init.assert_called_once()


class TestPowerflowServiceCalculate:
    """Tests for PowerflowService calculate_powerflow."""

    @pytest.mark.asyncio
    async def test_calculate_powerflow_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Test calculate_powerflow success flow."""
        with patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class, \
             patch.object(Powerflow, "from_modbus") as mock_from_modbus, \
             patch.object(Powerflow, "is_not_valid_with_last", return_value=False):

            mock_modbus = AsyncMock()
            mock_modbus.get_data.return_value = {"leader": mock_modbus_unit}
            mock_modbus_class.return_value = mock_modbus

            # Create a valid powerflow mock
            mock_powerflow = MagicMock()
            mock_powerflow.is_valid.return_value = True
            mock_powerflow.pv_production = 1000
            mock_powerflow.inverter = MagicMock(power=900)
            mock_powerflow.consumer = MagicMock(house=500, evcharger=0)
            mock_powerflow.grid = MagicMock(power=300)
            mock_powerflow.battery = MagicMock(power=0)
            mock_powerflow.mqtt_topic.return_value = "powerflow"
            mock_powerflow.prepare_point.return_value = MagicMock()
            mock_from_modbus.return_value = mock_powerflow

            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            await service.calculate_powerflow(None)

            mock_modbus.get_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_calculate_powerflow_no_leader(
        self, mock_service_settings, mock_event_bus
    ):
        """Test calculate_powerflow raises when no leader in units."""
        with patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class:
            mock_modbus = AsyncMock()
            mock_modbus.get_data.return_value = {"follower": MagicMock()}
            mock_modbus_class.return_value = mock_modbus

            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            with pytest.raises(InvalidDataException) as exc_info:
                await service.calculate_powerflow(None)

            assert "Invalid modbus data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_calculate_powerflow_invalid_battery(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Test calculate_powerflow raises when battery is invalid."""
        with patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class:
            mock_modbus = AsyncMock()

            # Make battery invalid
            mock_modbus_unit.batteries["battery0"].is_valid = False
            mock_modbus.get_data.return_value = {"leader": mock_modbus_unit}
            mock_modbus_class.return_value = mock_modbus

            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            with pytest.raises(InvalidDataException) as exc_info:
                await service.calculate_powerflow(None)

            assert "Invalid battery data" in exc_info.value.message


class TestPowerflowServiceWriteInfluxDB:
    """Tests for PowerflowService write_to_influxdb."""

    @pytest.mark.asyncio
    async def test_write_to_influxdb(
        self, mock_service_settings, mock_event_bus, mock_influxdb
    ):
        """Test write_to_influxdb writes points."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, mock_influxdb
            )

            # Create mock powerflow
            mock_powerflow = MagicMock()
            mock_powerflow.prepare_point.return_value = MagicMock()

            # Create mock battery
            mock_battery = MagicMock()
            mock_battery.prepare_point.return_value = MagicMock()

            await service.write_to_influxdb(
                {"leader": mock_powerflow},
                {"battery0": mock_battery}
            )

            mock_influxdb.write_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_influxdb_none(
        self, mock_service_settings, mock_event_bus
    ):
        """Test write_to_influxdb does nothing when influxdb is None."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            # Should not raise
            await service.write_to_influxdb({}, {})


class TestPowerflowServicePublish:
    """Tests for PowerflowService publish methods."""

    @pytest.mark.asyncio
    async def test_publish_modbus(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Test publish_modbus emits events."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            await service.publish_modbus({"leader": mock_modbus_unit})

            # Should emit events for inverter, meter, and battery
            assert mock_event_bus.emit.call_count >= 3

    @pytest.mark.asyncio
    async def test_publish_wallbox_with_data(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_wallbox with wallbox data."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            mock_wallbox_data = MagicMock()
            mock_wallbox_data.mqtt_topic.return_value = "wallbox"

            await service.publish_wallbox(mock_wallbox_data)

            mock_event_bus.emit.assert_called_once()
            call_args = mock_event_bus.emit.call_args
            assert isinstance(call_args[0][0], MQTTPublishEvent)

    @pytest.mark.asyncio
    async def test_publish_wallbox_none(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_wallbox with None data."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            await service.publish_wallbox(None)

            mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_powerflow_without_followers(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_powerflow without followers."""
        mock_service_settings.modbus.has_followers = False

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            mock_powerflow = MagicMock()
            mock_powerflow.mqtt_topic.return_value = "powerflow"

            await service.publish_powerflow({"leader": mock_powerflow})

            # Should emit MQTT event and PowerflowGeneratedEvent
            assert mock_event_bus.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_publish_powerflow_with_followers(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_powerflow with followers."""
        mock_service_settings.modbus.has_followers = True

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            mock_powerflow1 = MagicMock()
            mock_powerflow1.mqtt_topic.return_value = "powerflow/leader"
            mock_powerflow2 = MagicMock()
            mock_powerflow2.mqtt_topic.return_value = "powerflow/cumulated"

            await service.publish_powerflow({
                "leader": mock_powerflow1,
                "cumulated": mock_powerflow2
            })

            # Should emit MQTT events for each powerflow plus PowerflowGeneratedEvent
            assert mock_event_bus.emit.call_count == 3


class TestPowerflowServiceClose:
    """Tests for PowerflowService close."""

    @pytest.mark.asyncio
    async def test_close_with_wallbox(
        self, mock_service_settings, mock_event_bus
    ):
        """Test close closes wallbox."""
        mock_service_settings.is_wallbox_configured = True

        with patch("solaredge2mqtt.services.powerflow.Modbus"), patch(
            "solaredge2mqtt.services.powerflow.WallboxClient"
        ) as mock_wallbox_class:
            mock_wallbox = AsyncMock()
            mock_wallbox_class.return_value = mock_wallbox

            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            await service.close()

            mock_wallbox.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_wallbox(
        self, mock_service_settings, mock_event_bus
    ):
        """Test close without wallbox."""
        mock_service_settings.is_wallbox_configured = False

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(
                mock_service_settings, mock_event_bus, None
            )

            # Should not raise
            await service.close()
