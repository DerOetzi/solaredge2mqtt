"""Tests for Modbus service with mocking."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymodbus.exceptions import ModbusException

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.modbus import Modbus
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent, ModbusWriteEvent
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecInverterInfoRegister,
)


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()
    settings.modbus = MagicMock()
    settings.modbus.host = "192.168.1.100"  # noqa: S1313
    settings.modbus.port = 1502
    settings.modbus.timeout = 5
    settings.modbus.unit = 1
    settings.modbus.has_followers = False
    settings.modbus.check_grid_status = True
    settings.modbus.advanced_power_controls_enabled = False

    # Create unit settings
    mock_unit_settings = MagicMock()
    mock_unit_settings.unit = 1
    mock_unit_settings.host = None
    mock_unit_settings.port = None
    mock_unit_settings.role = "leader"
    mock_unit_settings.meter = [True, False, False]
    mock_unit_settings.battery = [True, False]

    settings.modbus.units = {"leader": mock_unit_settings}
    settings.modbus.debounce_cycles = 0

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
        modbus = Modbus(mock_service_settings)

        assert modbus.settings is mock_service_settings.modbus
        assert modbus._clients == {}
        assert modbus._initialized is False
        mock_event_bus.register.assert_called_once_with(modbus)

    def test_modbus_subscribes_to_events(self, mock_service_settings, mock_event_bus):
        """Test Modbus registers for decorated event handlers."""
        Modbus(mock_service_settings)

        mock_event_bus.register.assert_called_once()


class TestModbusAsyncInit:
    """Tests for Modbus async_init."""

    @pytest.mark.asyncio
    async def test_async_init(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test async_init initializes clients and detects devices."""
        modbus = Modbus(mock_service_settings)
        modbus.detect_devices = AsyncMock()
        modbus.check_readable_registers = AsyncMock()

        with patch(
            "solaredge2mqtt.services.modbus.asyncio.sleep", new_callable=AsyncMock
        ):
            await modbus.async_init()

        assert "leader" in modbus._clients
        modbus.detect_devices.assert_called_once()
        modbus.check_readable_registers.assert_called_once()
        assert modbus._initialized is True

    @pytest.mark.asyncio
    async def test_async_init_logs_unreadable_registers(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """async_init should warn when unreadable registers were blocked."""
        modbus = Modbus(mock_service_settings)
        modbus.detect_devices = AsyncMock()
        modbus.check_readable_registers = AsyncMock()
        modbus._block_unreadable = {40000}

        with (
            patch(
                "solaredge2mqtt.services.modbus.asyncio.sleep", new_callable=AsyncMock
            ),
            patch("solaredge2mqtt.services.modbus.logger.warning") as warn_mock,
        ):
            await modbus.async_init()

        warn_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_devices_calls_meter_and_battery_detection(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """detect_devices should read inverter info and run detectors."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus.read_device_info = AsyncMock(return_value={"meter0": 1})
        modbus._detect_meters = AsyncMock()
        modbus._detect_batteries = AsyncMock()

        await modbus.detect_devices()

        modbus.read_device_info.assert_called_once()
        modbus._detect_meters.assert_called_once()
        modbus._detect_batteries.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_data_exception_sets_offline(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """get_data should set offline and re-raise on exception."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._device_info = {"leader": {"inverter": MagicMock()}}
        modbus._get_raw_data = AsyncMock(
            side_effect=InvalidDataException("Invalid data")
        )

        with pytest.raises(InvalidDataException):
            await modbus.get_data()

    @pytest.mark.asyncio
    async def test_async_init_exception_sets_offline(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """async_init should set offline state and re-raise on exception."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus.detect_devices = AsyncMock(
            side_effect=InvalidDataException("Invalid data")
        )

        with pytest.raises(InvalidDataException):
            await modbus.async_init()

    @pytest.mark.asyncio
    async def test_detect_devices_exception_sets_offline(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """detect_devices should set offline state and re-raise on exception."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus.read_device_info = AsyncMock(
            side_effect=InvalidDataException("Invalid data")
        )

        with pytest.raises(InvalidDataException):
            await modbus.detect_devices()

    @pytest.mark.asyncio
    async def test_check_readable_registers_reads_all_units(
        self, mock_service_settings, mock_event_bus
    ):
        """check_readable_registers should iterate all configured units."""
        modbus = Modbus(mock_service_settings)
        modbus._get_raw_data = AsyncMock(return_value=({}, {}, {}))

        with patch("solaredge2mqtt.services.modbus.AsyncModbusTcpClient") as client_cls:
            client = AsyncMock()
            client_cls.return_value = client

            await modbus.check_readable_registers()

        modbus._get_raw_data.assert_called_once()
        call_args = modbus._get_raw_data.call_args
        assert call_args[0][0] == "leader"
        assert call_args[0][1] == 1

    @pytest.mark.asyncio
    async def test_read_device_info_stores_discovered_device(
        self, mock_service_settings, mock_event_bus
    ):
        """read_device_info stores ModbusDeviceInfo in internal map."""
        modbus = Modbus(mock_service_settings)
        modbus._device_info = {"leader": {}}
        modbus._read_from_modbus = AsyncMock(return_value={"c_model": "X"})

        mock_info = MagicMock()
        modbus._clients = {"leader": AsyncMock()}
        with patch(
            "solaredge2mqtt.services.modbus.ModbusDeviceInfo.from_sunspec",
            return_value=mock_info,
        ):
            result = await modbus.read_device_info(
                SunSpecInverterInfoRegister,
                "leader",
                "inverter",
                mock_service_settings.modbus.units["leader"],
            )

        assert result == {"c_model": "X"}
        assert modbus._device_info["leader"]["inverter"] is mock_info


class TestModbusAsyncInitFollowerWithOwnIp:
    """Tests for async_init with followers that have their own IP."""

    def _make_settings(
        self,
        mock_event_bus: object,
        follower_host: str | None,
        follower_port: int | None = None,
    ) -> MagicMock:
        settings = MagicMock()
        settings.modbus.host = "192.168.1.10"  # noqa: S1313
        settings.modbus.port = 1502
        settings.modbus.timeout = 1
        settings.modbus.debounce_cycles = 0
        settings.modbus.has_followers = True

        leader_unit = MagicMock()
        leader_unit.unit = 1
        leader_unit.host = None
        leader_unit.port = None

        follower_unit = MagicMock()
        follower_unit.unit = 2
        follower_unit.host = follower_host
        follower_unit.port = follower_port

        settings.modbus.units = {"leader": leader_unit, "follower0": follower_unit}
        settings.modbus.follower = [follower_unit]
        return settings

    @pytest.mark.asyncio
    async def test_async_init_builds_dedicated_client_for_follower_with_host(
        self, mock_event_bus
    ):
        """async_init builds a separate client for a follower with its own host."""
        settings = self._make_settings(mock_event_bus, "192.168.1.11")  # noqa: S1313

        modbus = Modbus(settings)
        modbus.detect_devices = AsyncMock()
        modbus.check_readable_registers = AsyncMock()

        created_clients: list[tuple[str, int]] = []

        def capture_client(host: str, port: int, **_kwargs: object) -> AsyncMock:
            created_clients.append((host, port))
            return AsyncMock()

        with (
            patch(
                "solaredge2mqtt.services.modbus.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "solaredge2mqtt.services.modbus.AsyncModbusTcpClient",
                side_effect=capture_client,
            ),
        ):
            await modbus.async_init()

        assert ("192.168.1.10", 1502) in created_clients  # noqa: S1313
        assert ("192.168.1.11", 1502) in created_clients  # noqa: S1313
        assert "leader" in modbus._clients
        assert "follower0" in modbus._clients
        assert modbus._clients["leader"] is not modbus._clients["follower0"]

    @pytest.mark.asyncio
    async def test_async_init_follower_without_host_reuses_leader_client(
        self, mock_event_bus
    ):
        """async_init reuses the leader client for a follower without its own host."""
        settings = self._make_settings(mock_event_bus, None)

        modbus = Modbus(settings)
        modbus.detect_devices = AsyncMock()
        modbus.check_readable_registers = AsyncMock()

        with (
            patch(
                "solaredge2mqtt.services.modbus.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "solaredge2mqtt.services.modbus.AsyncModbusTcpClient",
                return_value=AsyncMock(),
            ) as client_cls,
        ):
            await modbus.async_init()

        assert client_cls.call_count == 1
        assert modbus._clients["leader"] is modbus._clients["follower0"]

    @pytest.mark.asyncio
    async def test_async_init_follower_uses_custom_port(self, mock_event_bus):
        """async_init should use the follower's custom port when specified."""
        settings = self._make_settings(mock_event_bus, "192.168.1.11", 502)  # noqa: S1313

        modbus = Modbus(settings)
        modbus.detect_devices = AsyncMock()
        modbus.check_readable_registers = AsyncMock()

        created_clients: list[tuple[str, int]] = []

        def capture_client(host: str, port: int, **_kwargs: object) -> AsyncMock:
            created_clients.append((host, port))
            return AsyncMock()

        with (
            patch(
                "solaredge2mqtt.services.modbus.asyncio.sleep", new_callable=AsyncMock
            ),
            patch(
                "solaredge2mqtt.services.modbus.AsyncModbusTcpClient",
                side_effect=capture_client,
            ),
        ):
            await modbus.async_init()

        assert ("192.168.1.11", 502) in created_clients  # noqa: S1313


class TestModbusRawDataCollection:
    """Tests for _get_raw_data and block handling."""

    @pytest.mark.asyncio
    async def test_get_raw_data_reads_grid_advanced_meter_battery(
        self, mock_service_settings, mock_event_bus
    ):
        """_get_raw_data should include optional and detected payloads."""
        mock_service_settings.modbus.check_grid_status = True
        mock_service_settings.modbus.advanced_power_controls_enabled = True

        modbus = Modbus(mock_service_settings)
        modbus._device_info = {
            "leader": {
                "inverter": MagicMock(),
                "meter0": MagicMock(),
                "battery0": MagicMock(),
            }
        }

        with (
            patch(
                "solaredge2mqtt.services.modbus.SunSpecInverterRegister.request_bundles",
                return_value=[MagicMock()],
            ),
            patch(
                "solaredge2mqtt.services.modbus.SunSpecGridStatusRegister.request_bundles",
                return_value=[MagicMock()],
            ),
            patch(
                "solaredge2mqtt.services.modbus.SunSpecPowerControlRegister.request_bundles",
                return_value=[MagicMock()],
            ),
            patch(
                "solaredge2mqtt.services.modbus.SunSpecMeterRegister.request_bundles",
                return_value=[MagicMock()],
            ),
            patch(
                "solaredge2mqtt.services.modbus.SunSpecBatteryRegister.request_bundles",
                return_value=[MagicMock()],
            ),
        ):
            modbus._read_from_modbus = AsyncMock(
                side_effect=[
                    {"status": 4},
                    {"grid_status": 0},
                    {"advanced_power_control_enable": 1},
                    {"power": 100},
                    {"soe": 80},
                ]
            )

            inverter_raw, meters_raw, batteries_raw = await modbus._get_raw_data(
                "leader", 1
            )

        assert "status" in inverter_raw
        assert "grid_status" in inverter_raw
        assert "advanced_power_control_enable" in inverter_raw
        assert "meter0" in meters_raw
        assert "battery0" in batteries_raw

    @pytest.mark.asyncio
    async def test_get_raw_data_without_optionals(
        self, mock_service_settings, mock_event_bus
    ):
        """_get_raw_data should skip optional reads when disabled."""
        mock_service_settings.modbus.check_grid_status = False
        mock_service_settings.modbus.advanced_power_controls_enabled = False

        modbus = Modbus(mock_service_settings)
        modbus._device_info = {"leader": {"inverter": MagicMock()}}

        with patch(
            "solaredge2mqtt.services.modbus.SunSpecInverterRegister.request_bundles",
            return_value=[MagicMock()],
        ):
            modbus._read_from_modbus = AsyncMock(return_value={"status": 4})
            inverter_raw, meters_raw, batteries_raw = await modbus._get_raw_data(
                "leader", 1
            )

        assert inverter_raw == {"status": 4}
        assert meters_raw == {}
        assert batteries_raw == {}

    def test_block_register_noop_when_initialized(
        self, mock_service_settings, mock_event_bus
    ):
        """_block_register should not add blocks after initialization."""
        modbus = Modbus(mock_service_settings)
        modbus._initialized = True

        modbus._block_register(40000)

        assert 40000 not in modbus._block_unreadable


class TestModbusReadFromModbus:
    """Tests for Modbus _read_from_modbus."""

    @pytest.mark.asyncio
    async def test_read_from_modbus_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test successful modbus read."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}

        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10
        mock_bundle.decode_response.return_value = {"field": "value"}

        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [1, 2, 3]
        mock_modbus_client.read_holding_registers.return_value = mock_result

        result = await modbus._read_from_modbus([mock_bundle], "leader", 1)

        assert result == {"field": "value"}
        mock_modbus_client.read_holding_registers.assert_called_once()

    @pytest.mark.asyncio
    async def test_read_from_modbus_success_when_initialized(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Successful read should also work when service is already initialized."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._initialized = True

        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 2
        mock_bundle.decode_response.return_value = {"value": 1}

        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [1, 2]
        mock_modbus_client.read_holding_registers.return_value = mock_result

        result = await modbus._read_from_modbus([mock_bundle], "leader", 1)

        assert result == {"value": 1}

    @pytest.mark.asyncio
    async def test_read_from_modbus_error_blocks_register(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus read error blocks register."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._initialized = False

        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10

        mock_result = MagicMock()
        mock_result.isError.return_value = True
        mock_modbus_client.read_holding_registers.return_value = mock_result

        await modbus._read_from_modbus([mock_bundle], "leader", 1)

        assert 40000 in modbus._block_unreadable

    @pytest.mark.asyncio
    async def test_read_from_modbus_exception_blocks_register(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus exception blocks register."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._initialized = False

        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10

        mock_modbus_client.read_holding_registers.side_effect = ModbusException(
            "Test error"
        )

        await modbus._read_from_modbus([mock_bundle], "leader", 1)

        assert 40000 in modbus._block_unreadable

    @pytest.mark.asyncio
    async def test_read_from_modbus_skips_blocked_register(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus read skips blocked registers."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._block_unreadable = {40000}

        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 10

        await modbus._read_from_modbus([mock_bundle], "leader", 1)

        mock_modbus_client.read_holding_registers.assert_not_called()

    @pytest.mark.asyncio
    async def test_read_from_modbus_uses_explicit_client_override(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Explicit client parameter overrides the stored client for the unit."""
        modbus = Modbus(mock_service_settings)
        stored_client = AsyncMock()
        modbus._clients = {"leader": stored_client}

        mock_bundle = MagicMock()
        mock_bundle.address = 40000
        mock_bundle.length = 2
        mock_bundle.decode_response.return_value = {"v": 1}

        mock_result = MagicMock()
        mock_result.isError.return_value = False
        mock_result.registers = [1]
        mock_modbus_client.read_holding_registers.return_value = mock_result

        await modbus._read_from_modbus(
            [mock_bundle], "leader", 1, client=mock_modbus_client
        )

        mock_modbus_client.read_holding_registers.assert_called_once()
        stored_client.read_holding_registers.assert_not_called()


class TestModbusGetData:
    """Tests for Modbus get_data."""

    @pytest.mark.asyncio
    async def test_get_data_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test get_data returns units."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._initialized = True

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

        modbus._get_raw_data = AsyncMock(return_value=({}, {}, {}))

        with patch("solaredge2mqtt.services.modbus.ModbusUnit") as mock_unit_class:
            mock_unit_instance = MagicMock()
            mock_unit_class.return_value = mock_unit_instance

            mock_inverter = MagicMock()
            mock_inverter.info = mock_info
            mock_inverter.info.unit = mock_unit_info
            modbus._map_inverter = MagicMock(return_value=mock_inverter)
            modbus._map_meters = MagicMock(return_value={})
            modbus._map_batteries = MagicMock(return_value={})

            await modbus.get_data()

            assert mock_event_bus.emit.call_count >= 1
            emitted_types = [type(c[0][0]) for c in mock_event_bus.emit.call_args_list]
            assert ModbusUnitsReadEvent in emitted_types

    @pytest.mark.asyncio
    async def test_get_data_key_error(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test get_data raises on KeyError."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}
        modbus._initialized = True
        modbus._device_info = {}

        modbus._get_raw_data = AsyncMock(side_effect=KeyError("missing key"))

        with pytest.raises(InvalidDataException):
            await modbus.get_data()


class TestModbusMappers:
    """Tests for Modbus mapper methods."""

    def test_map_inverter(
        self, mock_service_settings, mock_event_bus, mock_device_info
    ):
        """Test _map_inverter creates ModbusInverter."""
        modbus = Modbus(mock_service_settings)
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
            mock_inverter_class.from_sunspec.return_value = mock_inverter

            result = modbus._map_inverter("leader", {})

            assert result is mock_inverter

    def test_map_meters(self, mock_service_settings, mock_event_bus, mock_device_info):
        """Test _map_meters creates ModbusMeter dict."""
        modbus = Modbus(mock_service_settings)
        modbus._device_info = {"leader": {"meter0": mock_device_info}}

        with patch("solaredge2mqtt.services.modbus.ModbusMeter") as mock_meter_class:
            mock_meter = MagicMock()
            mock_meter.info = mock_device_info
            mock_meter.power.actual = 500
            mock_meter.energy.totalimport = 10000
            mock_meter.energy.totalexport = 5000
            mock_meter_class.from_sunspec.return_value = mock_meter

            result = modbus._map_meters("leader", {"meter0": {}})

            assert "meter0" in result

    def test_map_batteries(
        self, mock_service_settings, mock_event_bus, mock_device_info
    ):
        """Test _map_batteries creates ModbusBattery dict."""
        modbus = Modbus(mock_service_settings)
        modbus._device_info = {"leader": {"battery0": mock_device_info}}

        with patch(
            "solaredge2mqtt.services.modbus.ModbusBattery"
        ) as mock_battery_class:
            mock_battery = MagicMock()
            mock_battery.info = mock_device_info
            mock_battery.status = "ON"
            mock_battery.power = 500
            mock_battery.state_of_charge = 80
            mock_battery_class.from_sunspec.return_value = mock_battery

            result = modbus._map_batteries("leader", {"battery0": {}})

            assert "battery0" in result
            assert result["battery0"] is mock_battery


class TestModbusWriteToModbus:
    """Tests for Modbus _write_to_modbus."""

    @pytest.mark.asyncio
    async def test_write_to_modbus_success(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test successful modbus write to leader."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}

        mock_register = MagicMock()
        mock_register.address = 40000
        mock_register.name = "test_register"
        mock_register.encode_request.return_value = [1, 2, 3]

        await modbus._write_to_modbus(mock_register, 100)

        mock_modbus_client.write_registers.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_to_modbus_uses_unit_settings_device_id(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """
        _write_to_modbus should use the unit's device_id
        and client for the given unit_key.
        """
        follower_client = AsyncMock()
        follower_unit = MagicMock()
        follower_unit.unit = 3
        mock_service_settings.modbus.units = {
            "leader": mock_service_settings.modbus.units["leader"],
            "follower0": follower_unit,
        }

        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client, "follower0": follower_client}

        mock_register = MagicMock()
        mock_register.address = 40000
        mock_register.name = "test_register"
        mock_register.encode_request.return_value = [1, 2, 3]

        await modbus._write_to_modbus(mock_register, 100, unit_key="follower0")

        follower_client.write_registers.assert_called_once()
        mock_modbus_client.write_registers.assert_not_called()
        assert follower_client.write_registers.call_args.kwargs["device_id"] == 3

    @pytest.mark.asyncio
    async def test_write_to_modbus_exception(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test modbus write handles exception."""
        modbus = Modbus(mock_service_settings)
        modbus._clients = {"leader": mock_modbus_client}

        mock_register = MagicMock()
        mock_register.address = 40000
        mock_register.name = "test_register"
        mock_register.encode_request.return_value = [1, 2, 3]

        mock_modbus_client.write_registers.side_effect = ModbusException("Write error")

        await modbus._write_to_modbus(mock_register, 100)


class TestModbusHandleWriteEvent:
    """Tests for Modbus _handle_write_event."""

    @pytest.mark.asyncio
    async def test_handle_write_event(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test handling write event passes register, payload and unit_key."""
        modbus = Modbus(mock_service_settings)
        modbus._write_to_modbus = AsyncMock()

        mock_register = MagicMock()
        event = ModbusWriteEvent(mock_register, 100)

        await modbus._handle_write_event(event)

        modbus._write_to_modbus.assert_called_once_with(mock_register, 100, "leader")

    @pytest.mark.asyncio
    async def test_handle_write_event_with_follower_unit_key(
        self, mock_service_settings, mock_event_bus, mock_modbus_client
    ):
        """Test handling write event forwards custom unit_key to _write_to_modbus."""
        modbus = Modbus(mock_service_settings)
        modbus._write_to_modbus = AsyncMock()

        mock_register = MagicMock()
        event = ModbusWriteEvent(mock_register, 50, unit_key="follower0")

        await modbus._handle_write_event(event)

        modbus._write_to_modbus.assert_called_once_with(mock_register, 50, "follower0")
