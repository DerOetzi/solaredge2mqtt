"""Tests for Modbus service with mocking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.exceptions import ModbusException

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.modbus import Modbus
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent, ModbusWriteEvent


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()
    settings.modbus = MagicMock()
    settings.modbus.host = "192.168.1.100"
    settings.modbus.port = 1502
    settings.modbus.timeout = 5
    settings.modbus.unit = 1
    settings.modbus.has_followers = False
    settings.modbus.check_grid_status = True
    settings.modbus.advanced_power_controls_enabled = False

    # Create unit settings
    mock_unit_settings = MagicMock()
    mock_unit_settings.unit = 1
    mock_unit_settings.role = "leader"
    mock_unit_settings.meter = [True, False, False]
    mock_unit_settings.battery = [True, False]

    settings.modbus.units = {"leader": mock_unit_settings}

    return settings


@pytest.fixture
def mock_modbus_client():
    """Mock pymodbus client."""
    with patch(
        "solaredge2mqtt.services.modbus.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_device_info():
    """Create mock device info."""
    info = MagicMock()
    info.manufacturer = "SolarEdge"
    info.model = "SE10K"
    info.serialnumber = "12345"
    info.unit_key.return_value = "leader:"
    return info


class TestModbusInit:
    """Tests for Modbus initialization."""

    def test_modbus_init(self, mock_service_settings, mock_event_bus):
        """Test Modbus initialization."""
        modbus = Modbus(mock_service_settings, mock_event_bus)

        assert modbus.settings is mock_service_settings.modbus
        assert modbus.event_bus is mock_event_bus
        assert modbus.client is None
        assert modbus._initialized is False

    def test_modbus_subscribes_to_events(
        self, mock_service_settings, mock_event_bus
    ):
        """Test Modbus subscribes to write events."""
        modbus = Modbus(mock_service_settings, mock_event_bus)

        mock_event_bus.subscribe.assert_called()


class TestModbusAsyncInit:
    """Tests for Modbus async_init."""

    @pytest.mark.asyncio
    async def test_async_init(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test async_init initializes client and detects devices."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.detect_devices = AsyncMock()
        modbus.check_readable_registers = AsyncMock()

        with patch("solaredge2mqtt.services.modbus.asyncio.sleep", new_callable=AsyncMock):
            await modbus.async_init()

        assert modbus.client is not None
        modbus.detect_devices.assert_called_once()
        modbus.check_readable_registers.assert_called_once()
        assert modbus._initialized is True


class TestModbusReadFromModbus:
    """Tests for Modbus _read_from_modbus."""

    @pytest.mark.asyncio
    async def test_read_from_modbus_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test successful modbus read."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client

        # Mock register bundle
        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10
        mock_bundle.decode_response.return_value = {"field": "value"}

        # Mock successful read
        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [1, 2, 3]
        mock_modbus_client.read_holding_registers.return_value = mock_result

        result = await modbus._read_from_modbus([mock_bundle], 1)

        assert result == {"field": "value"}
        mock_modbus_client.read_holding_registers.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_from_modbus_error_blocks_register(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus read error blocks register."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client
        modbus._initialized = False

        # Mock register bundle
        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10

        # Mock error result
        mock_result = MagicMock()
        mock_result.isError.return_value = True
        mock_modbus_client.read_holding_registers.return_value = mock_result

        await modbus._read_from_modbus([mock_bundle], 1)

        assert 40000 in modbus._block_unreadable

    @pytest.mark.asyncio
    async def test_read_from_modbus_exception_blocks_register(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus exception blocks register."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client
        modbus._initialized = False

        # Mock register bundle
        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10

        # Mock exception
        mock_modbus_client.read_holding_registers.side_effect = ModbusException("Test error")

        await modbus._read_from_modbus([mock_bundle], 1)

        assert 40000 in modbus._block_unreadable

    @pytest.mark.asyncio
    async def test_read_from_modbus_skips_blocked_register(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus read skips blocked registers."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client
        modbus._block_unreadable = {40000}

        # Mock register bundle for blocked address
        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10

        await modbus._read_from_modbus([mock_bundle], 1)

        # Should not have called read
        mock_modbus_client.read_holding_registers.assert_not_called()


class TestModbusGetData:
    """Tests for Modbus get_data."""

    @pytest.mark.asyncio
    async def test_get_data_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test get_data returns units."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client
        modbus._initialized = True

        # Setup device info
        mock_info = MagicMock()
        mock_unit_info = MagicMock()
        mock_unit_info.unit = 1
        mock_unit_info.key = "leader"
        mock_unit_info.role = "leader"
        mock_info.unit = mock_unit_info
        modbus._device_info = {
            "leader": {
                "inverter": mock_info,
            }
        }

        # Mock _get_raw_data
        modbus._get_raw_data = AsyncMock(return_value=({}, {}, {}))

        # Mock mappers - create properly structured mock objects
        with patch(
            "solaredge2mqtt.services.modbus.ModbusUnit"
        ) as mock_unit_class:
            mock_unit_instance = MagicMock()
            mock_unit_class.return_value = mock_unit_instance

            # Mock _map_inverter to return a proper mock
            mock_inverter = MagicMock()
            mock_inverter.info = mock_info
            mock_inverter.info.unit = mock_unit_info
            modbus._map_inverter = MagicMock(return_value=mock_inverter)
            modbus._map_meters = MagicMock(return_value={})
            modbus._map_batteries = MagicMock(return_value={})

            result = await modbus.get_data()

            # Should emit event
            mock_event_bus.emit.assert_called_once()
            call_args = mock_event_bus.emit.call_args
            assert isinstance(call_args[0][0], ModbusUnitsReadEvent)

    @pytest.mark.asyncio
    async def test_get_data_key_error(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test get_data raises on KeyError."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client
        modbus._initialized = True
        modbus._device_info = {}

        # Mock _get_raw_data to raise KeyError
        modbus._get_raw_data = AsyncMock(side_effect=KeyError("missing key"))

        with pytest.raises(InvalidDataException):
            await modbus.get_data()


class TestModbusMappers:
    """Tests for Modbus mapper methods."""

    def test_map_inverter(
        self, mock_service_settings, mock_event_bus, mock_device_info
    ):
        """Test _map_inverter creates ModbusInverter."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus._device_info = {"leader": {"inverter": mock_device_info}}

        with patch(
            "solaredge2mqtt.services.modbus.ModbusInverter"
        ) as mock_inverter_class:
            mock_inverter = MagicMock()
            mock_inverter.info = mock_device_info
            mock_inverter.status = "ON"
            mock_inverter.ac.power.actual = 1000
            mock_inverter.dc.power = 1200
            mock_inverter.energytotal = 50000
            mock_inverter.grid_status = "ON"
            mock_inverter_class.return_value = mock_inverter

            result = modbus._map_inverter("leader", {})

            assert result is mock_inverter

    def test_map_meters(
        self, mock_service_settings, mock_event_bus, mock_device_info
    ):
        """Test _map_meters creates ModbusMeter dict."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus._device_info = {"leader": {"meter0": mock_device_info}}

        with patch(
            "solaredge2mqtt.services.modbus.ModbusMeter"
        ) as mock_meter_class:
            mock_meter = MagicMock()
            mock_meter.info = mock_device_info
            mock_meter.power.actual = 500
            mock_meter.energy.totalimport = 10000
            mock_meter.energy.totalexport = 5000
            mock_meter_class.return_value = mock_meter

            result = modbus._map_meters("leader", {"meter0": {}})

            assert "meter0" in result

    def test_map_batteries(
        self, mock_service_settings, mock_event_bus, mock_device_info
    ):
        """Test _map_batteries creates ModbusBattery dict."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus._device_info = {"leader": {"battery0": mock_device_info}}

        with patch(
            "solaredge2mqtt.services.modbus.ModbusBattery"
        ) as mock_battery_class:
            mock_battery = MagicMock()
            mock_battery.info = mock_device_info
            mock_battery.status = "ON"
            mock_battery.power = 500
            mock_battery.state_of_charge = 80
            mock_battery_class.return_value = mock_battery

            result = modbus._map_batteries("leader", {"battery0": {}})

            assert "battery0" in result


class TestModbusWriteToModbus:
    """Tests for Modbus _write_to_modbus."""

    @pytest.mark.asyncio
    async def test_write_to_modbus_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test successful modbus write."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client

        mock_register = MagicMock()
        mock_register.address = 40000
        mock_register.name = "test_register"
        mock_register.encode_request.return_value = [1, 2, 3]

        await modbus._write_to_modbus(mock_register, 100)

        mock_modbus_client.write_registers.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_modbus_exception(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus write handles exception."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus.client = mock_modbus_client

        mock_register = MagicMock()
        mock_register.address = 40000
        mock_register.name = "test_register"
        mock_register.encode_request.return_value = [1, 2, 3]

        mock_modbus_client.write_registers.side_effect = ModbusException("Write error")

        # Should not raise, just log error
        await modbus._write_to_modbus(mock_register, 100)


class TestModbusHandleWriteEvent:
    """Tests for Modbus _handle_write_event."""

    @pytest.mark.asyncio
    async def test_handle_write_event(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test handling write event."""
        modbus = Modbus(mock_service_settings, mock_event_bus)
        modbus._write_to_modbus = AsyncMock()

        mock_register = MagicMock()
        event = ModbusWriteEvent(mock_register, 100)

        await modbus._handle_write_event(event)

        modbus._write_to_modbus.assert_called_once_with(mock_register, 100)
