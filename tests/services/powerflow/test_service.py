"""Tests for PowerflowService with mocking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import (
    ConfigurationException,
    InvalidDataException,
)
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.powerflow import PowerflowService
from solaredge2mqtt.services.powerflow.models import (
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
    settings.wallbox.is_configured = False

    settings.location = MagicMock()
    settings.location.latitude = 52.52
    settings.location.longitude = 13.405

    return settings


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()
    return event_bus


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
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            assert service.settings is mock_service_settings
            assert service.event_bus is mock_event_bus
            assert service.influxdb is None
            assert service.wallbox is None

    def test_powerflow_service_init_with_wallbox(
        self, mock_service_settings, mock_event_bus
    ):
        """Test PowerflowService initialization with wallbox."""
        mock_service_settings.wallbox.is_configured = True

        with (
            patch("solaredge2mqtt.services.powerflow.Modbus"),
            patch("solaredge2mqtt.services.powerflow.WallboxClient"),
        ):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

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

            service = PowerflowService(mock_service_settings, mock_event_bus, None)
            await service.async_init()

            mock_modbus.async_init.assert_called_once()


class TestPowerflowServiceCalculate:
    """Tests for PowerflowService calculate_powerflow."""

    @pytest.mark.asyncio
    async def test_calculate_powerflow_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Test calculate_powerflow success flow."""
        with (
            patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class,
            patch.object(Powerflow, "from_modbus") as mock_from_modbus,
            patch.object(Powerflow, "is_not_valid_with_last", return_value=False),
        ):
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

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            await service.calculate_powerflow()

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

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

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

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            with pytest.raises(InvalidDataException) as exc_info:
                await service.calculate_powerflow()

            assert "Invalid battery data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_calculate_powerflow_invalid_powerflow_raises(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Invalid powerflow output raises InvalidDataException."""
        with (
            patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class,
            patch.object(Powerflow, "from_modbus") as mock_from_modbus,
            patch.object(Powerflow, "is_not_valid_with_last", return_value=False),
        ):
            mock_modbus = AsyncMock()
            mock_modbus.get_data.return_value = {"leader": mock_modbus_unit}
            mock_modbus_class.return_value = mock_modbus

            mock_powerflow = MagicMock()
            mock_powerflow.is_valid.return_value = False
            mock_powerflow.model_dump_json.return_value = "{}"
            mock_from_modbus.return_value = mock_powerflow

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            with pytest.raises(InvalidDataException) as exc_info:
                await service.calculate_powerflow()

            assert "Invalid powerflow data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_calculate_powerflow_delta_not_valid_raises(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Invalid delta to last powerflow raises InvalidDataException."""
        with (
            patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class,
            patch.object(Powerflow, "from_modbus") as mock_from_modbus,
            patch.object(Powerflow, "is_not_valid_with_last", return_value=True),
        ):
            mock_modbus = AsyncMock()
            mock_modbus.get_data.return_value = {"leader": mock_modbus_unit}
            mock_modbus_class.return_value = mock_modbus

            mock_powerflow = MagicMock()
            mock_powerflow.is_valid.return_value = True
            mock_powerflow.model_dump_json.return_value = "{}"
            mock_from_modbus.return_value = mock_powerflow

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            with pytest.raises(InvalidDataException) as exc_info:
                await service.calculate_powerflow()

            assert "Value change not valid" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_calculate_powerflow_followers_adds_cumulated(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """Followers path builds and publishes cumulated powerflow."""
        mock_service_settings.modbus.has_followers = True

        follower_unit = MagicMock()
        leader_powerflow = MagicMock()
        follower_powerflow = MagicMock()
        cumulated_powerflow = MagicMock()
        cumulated_powerflow.is_valid.return_value = True
        cumulated_powerflow.pv_production = 1500
        cumulated_powerflow.inverter = MagicMock(power=1300)
        cumulated_powerflow.consumer = MagicMock(house=700, evcharger=0)
        cumulated_powerflow.grid = MagicMock(power=400)
        cumulated_powerflow.battery = MagicMock(power=0)

        with (
            patch("solaredge2mqtt.services.powerflow.Modbus") as mock_modbus_class,
            patch.object(
                Powerflow, "cumulated_powerflow", return_value=cumulated_powerflow
            ) as mock_cumulated,
            patch.object(Powerflow, "is_not_valid_with_last", return_value=False),
        ):
            mock_modbus = AsyncMock()
            mock_modbus.get_data.return_value = {
                "leader": mock_modbus_unit,
                "follower": follower_unit,
            }
            mock_modbus_class.return_value = mock_modbus

            service = PowerflowService(mock_service_settings, mock_event_bus, None)
            service._check_batteries = MagicMock(return_value={})
            service._read_wallbox_data = AsyncMock(return_value=(0, None))
            service._powerflows_from_data = MagicMock(
                return_value={
                    "leader": leader_powerflow,
                    "follower": follower_powerflow,
                }
            )
            service.write_to_influxdb = AsyncMock()
            service.publish_modbus = AsyncMock()
            service.publish_wallbox = AsyncMock()
            service.publish_powerflow = AsyncMock()

            await service.calculate_powerflow()

            mock_cumulated.assert_called_once()
            cumulated_arg = mock_cumulated.call_args.args[0]
            assert cumulated_arg["leader"] is leader_powerflow
            assert cumulated_arg["follower"] is follower_powerflow
            service.publish_powerflow.assert_called_once()
            published = service.publish_powerflow.call_args.args[0]
            assert published["cumulated"] is cumulated_powerflow


class TestPowerflowServiceHelpers:
    """Tests for helper methods extracted from calculate_powerflow."""

    def test_check_batteries_returns_flat_map(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """The helper flattens batteries across all units."""
        follower_unit = MagicMock()
        follower_battery = MagicMock()
        follower_battery.is_valid = True
        follower_unit.batteries = {"battery1": follower_battery}

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            batteries = service._check_batteries(
                {"leader": mock_modbus_unit, "follower": follower_unit}
            )

            assert batteries == {
                "leader:battery0": mock_modbus_unit.batteries["battery0"],
                "follower:battery1": follower_battery,
            }

    def test_check_batteries_raises_for_invalid_data(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """The helper raises InvalidDataException for invalid battery payloads."""
        mock_modbus_unit.batteries["battery0"].is_valid = False

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            with pytest.raises(InvalidDataException) as exc_info:
                service._check_batteries({"leader": mock_modbus_unit})

            assert "Invalid battery data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_read_wallbox_data_without_wallbox_returns_default(
        self, mock_service_settings, mock_event_bus
    ):
        """The helper returns defaults when no wallbox is configured."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            evcharger, wallbox_data = await service._read_wallbox_data()

            assert evcharger == 0
            assert wallbox_data is None

    @pytest.mark.asyncio
    async def test_read_wallbox_data_success(
        self, mock_service_settings, mock_event_bus
    ):
        """The helper returns wallbox payload and power on success."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)
            wallbox_payload = MagicMock()
            wallbox_payload.power = 7400
            wallbox = AsyncMock()
            wallbox.get_data.return_value = wallbox_payload
            service.wallbox = wallbox

            evcharger, wallbox_data = await service._read_wallbox_data()

            assert evcharger == 7400
            assert wallbox_data is wallbox_payload

    @pytest.mark.asyncio
    async def test_read_wallbox_data_handles_configuration_exception(
        self, mock_service_settings, mock_event_bus
    ):
        """The helper keeps defaults when wallbox config is invalid."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)
            wallbox = AsyncMock()
            wallbox.get_data.side_effect = ConfigurationException(
                "wallbox", "not configured"
            )
            service.wallbox = wallbox

            evcharger, wallbox_data = await service._read_wallbox_data()

            assert evcharger == 0
            assert wallbox_data is None

    @pytest.mark.asyncio
    async def test_read_wallbox_data_handles_invalid_data_exception(
        self, mock_service_settings, mock_event_bus
    ):
        """The helper keeps defaults when wallbox payload is invalid."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)
            wallbox = AsyncMock()
            wallbox.get_data.side_effect = InvalidDataException("invalid")
            service.wallbox = wallbox

            evcharger, wallbox_data = await service._read_wallbox_data()

            assert evcharger == 0
            assert wallbox_data is None

    def test_powerflows_from_data_calls_leader_with_evcharger(
        self, mock_service_settings, mock_event_bus, mock_modbus_unit
    ):
        """The helper calls from_modbus with evcharger only for leader unit."""
        follower_unit = MagicMock()
        follower_unit.batteries = {}

        with (
            patch("solaredge2mqtt.services.powerflow.Modbus"),
            patch.object(Powerflow, "from_modbus") as mock_from_modbus,
        ):
            leader_powerflow = MagicMock()
            leader_powerflow.model_dump_json.return_value = "{}"
            follower_powerflow = MagicMock()
            follower_powerflow.model_dump_json.return_value = "{}"
            mock_from_modbus.side_effect = [leader_powerflow, follower_powerflow]

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            powerflows = service._powerflows_from_data(
                {"leader": mock_modbus_unit, "follower": follower_unit}, 7400
            )

            assert powerflows == {
                "leader": leader_powerflow,
                "follower": follower_powerflow,
            }
            mock_from_modbus.assert_any_call(mock_modbus_unit, 7400)
            mock_from_modbus.assert_any_call(follower_unit)
            assert mock_from_modbus.call_count == 2


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
                {"leader": mock_powerflow}, {"battery0": mock_battery}
            )

            mock_influxdb.write_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_influxdb_none(self, mock_service_settings, mock_event_bus):
        """Test write_to_influxdb does nothing when influxdb is None."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

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
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            await service.publish_modbus({"leader": mock_modbus_unit})

            # Should emit events for inverter, meter, and battery
            assert mock_event_bus.emit.call_count >= 3

    @pytest.mark.asyncio
    async def test_publish_wallbox_with_data(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_wallbox with wallbox data."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            mock_wallbox_data = MagicMock()
            mock_wallbox_data.mqtt_topic.return_value = "wallbox"

            await service.publish_wallbox(mock_wallbox_data)

            mock_event_bus.emit.assert_called_once()
            call_args = mock_event_bus.emit.call_args
            assert isinstance(call_args[0][0], MQTTPublishEvent)

    @pytest.mark.asyncio
    async def test_publish_wallbox_none(self, mock_service_settings, mock_event_bus):
        """Test publish_wallbox with None data."""
        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            await service.publish_wallbox(None)

            mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_powerflow_without_followers(
        self, mock_service_settings, mock_event_bus
    ):
        """Test publish_powerflow without followers."""
        mock_service_settings.modbus.has_followers = False

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

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
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            mock_powerflow1 = MagicMock()
            mock_powerflow1.mqtt_topic.return_value = "powerflow/leader"
            mock_powerflow2 = MagicMock()
            mock_powerflow2.mqtt_topic.return_value = "powerflow/cumulated"

            await service.publish_powerflow(
                {"leader": mock_powerflow1, "cumulated": mock_powerflow2}
            )

            # Should emit MQTT events for each powerflow plus PowerflowGeneratedEvent
            assert mock_event_bus.emit.call_count == 3


class TestPowerflowServiceClose:
    """Tests for PowerflowService close."""

    @pytest.mark.asyncio
    async def test_close_with_wallbox(self, mock_service_settings, mock_event_bus):
        """Test close closes wallbox."""
        mock_service_settings.wallbox.is_configured = True

        with (
            patch("solaredge2mqtt.services.powerflow.Modbus"),
            patch(
                "solaredge2mqtt.services.powerflow.WallboxClient"
            ) as mock_wallbox_class,
            patch(
                "solaredge2mqtt.services.powerflow.WallboxClient"
            ) as mock_wallbox_class,
        ):
            mock_wallbox = AsyncMock()
            mock_wallbox_class.return_value = mock_wallbox

            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            await service.close()

            mock_wallbox.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_without_wallbox(self, mock_service_settings, mock_event_bus):
        """Test close without wallbox."""
        mock_service_settings.is_wallbox_configured = False

        with patch("solaredge2mqtt.services.powerflow.Modbus"):
            service = PowerflowService(mock_service_settings, mock_event_bus, None)

            # Should not raise
            await service.close()
