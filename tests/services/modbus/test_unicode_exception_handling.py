"""Tests for Unicode exception handling in Modbus service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import InvalidRegisterDataException
from solaredge2mqtt.services.modbus import Modbus
from solaredge2mqtt.services.modbus.sunspec.meter import (
    SunSpecMeterOffset,
)


@pytest.fixture
def mock_service_settings():
    """Create mock service settings for testing."""
    settings = MagicMock()
    settings.modbus = MagicMock()
    settings.modbus.host = "192.168.1.100"
    settings.modbus.port = 1502
    settings.modbus.timeout = 5
    settings.modbus.unit = 1
    settings.modbus.has_followers = False
    settings.modbus.check_grid_status = True
    settings.modbus.advanced_power_controls_enabled = False

    # Create unit settings with meters enabled
    mock_unit_settings = MagicMock()
    mock_unit_settings.unit = 1
    mock_unit_settings.role = "leader"
    mock_unit_settings.meter = [True, True, True]  # All meters enabled
    mock_unit_settings.battery = [True, False]

    settings.modbus.units = {"leader": mock_unit_settings}

    return settings


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    return MagicMock()


@pytest.fixture
def mock_modbus_client():
    """Mock pymodbus client."""
    with patch(
        "solaredge2mqtt.services.modbus.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = AsyncMock()
        mock_client.connected = False
        mock_client_class.return_value = mock_client
        yield mock_client


class TestShouldDetectMeter:
    """Tests for _should_detect_meter method."""

    def test_should_detect_meter_enabled_and_present(self):
        """Test meter detection when enabled and present in data."""
        unit_settings = MagicMock()
        unit_settings.meter = [True, True, False]

        meter = SunSpecMeterOffset.METER0
        inverter_raw = {"meter0": 172, "meter1": 173}

        result = Modbus._should_detect_meter(
            unit_settings, meter, inverter_raw
        )

        assert result is True

    def test_should_detect_meter_disabled(self):
        """Test meter detection when disabled in settings."""
        unit_settings = MagicMock()
        unit_settings.meter = [False, True, False]

        meter = SunSpecMeterOffset.METER0
        inverter_raw = {"meter0": 172, "meter1": 173}

        result = Modbus._should_detect_meter(
            unit_settings, meter, inverter_raw
        )

        assert result is False

    def test_should_detect_meter_not_in_data(self):
        """Test meter detection when not present in inverter data."""
        unit_settings = MagicMock()
        unit_settings.meter = [True, True, False]

        meter = SunSpecMeterOffset.METER2
        inverter_raw = {"meter0": 172, "meter1": 173}

        result = Modbus._should_detect_meter(
            unit_settings, meter, inverter_raw
        )

        assert result is False

    def test_should_detect_meter_all_conditions_false(self):
        """Test meter detection when all conditions are false."""
        unit_settings = MagicMock()
        unit_settings.meter = [False, False, False]

        meter = SunSpecMeterOffset.METER0
        inverter_raw = {}

        result = Modbus._should_detect_meter(
            unit_settings, meter, inverter_raw
        )

        assert result is False


class TestLogMeterDetectionError:
    """Tests for _log_meter_detection_error method."""

    @patch("solaredge2mqtt.services.modbus.logger")
    def test_log_meter_detection_error_with_meter_address(
        self, mock_logger
    ):
        """Test error logging includes meter address from inverter."""
        meter_id = "meter1"
        inverter_raw = {
            "meter0": 172,
            "meter1": 173,
            "meter2": 174,
            "c_manufacturer": "SolarEdge",
            "c_model": "SE5000H",
            "c_serialnumber": "12345678",
            "c_version": "4.24.16",
        }

        exception = InvalidRegisterDataException(
            register_id="c_manufacturer",
            address=40123,
            raw_values=[0xC200, 0x0000],
            original_error=UnicodeDecodeError(
                "utf-8", b"\xc2", 0, 1, "invalid start byte"
            ),
        )

        Modbus._log_meter_detection_error(
            meter_id, inverter_raw, exception
        )

        # Check that error was logged
        assert mock_logger.error.call_count == 1
        error_call = mock_logger.error.call_args[0][0]
        assert "Skipping meter1" in error_call
        assert "invalid register data" in error_call

        # Check that info logs were called (now 4: address, inverter info, 
        # communication issue, and configuration hint)
        assert mock_logger.info.call_count == 4

        # Find info calls
        info_calls = [
            call[0][0] for call in mock_logger.info.call_args_list
        ]

        # Check meter address is logged
        meter_address_logged = any(
            "meter1=173" in call for call in info_calls
        )
        assert meter_address_logged

        # Check inverter info is logged
        inverter_info_logged = any(
            "SolarEdge" in call and "SE5000H" in call
            for call in info_calls
        )
        assert inverter_info_logged
        
        # Check configuration hint is logged with array index format
        config_hint_logged = any(
            "disable detection in configuration.yml" in call
            and "modbus.meter[1]" in call
            for call in info_calls
        )
        assert config_hint_logged

    @patch("solaredge2mqtt.services.modbus.logger")
    def test_log_meter_detection_error_without_meter_address(
        self, mock_logger
    ):
        """Test error logging when meter address not in data."""
        meter_id = "meter2"
        inverter_raw = {
            "meter0": 172,
            "meter1": 173,
            # meter2 not present
            "c_manufacturer": "SolarEdge",
            "c_model": "SE5000H",
            "c_serialnumber": "12345",
            "c_version": "4.24",
        }

        exception = InvalidRegisterDataException(
            register_id="c_model",
            address=40125,
            raw_values=[0xFFFF],
            original_error=UnicodeDecodeError(
                "utf-8", b"\xff", 0, 1, "invalid byte"
            ),
        )

        Modbus._log_meter_detection_error(
            meter_id, inverter_raw, exception
        )

        # Should still log error and info (now 4 info logs)
        assert mock_logger.error.call_count == 1
        assert mock_logger.info.call_count == 4

        # meter2 should still be logged (with None value from .get())
        info_calls = [
            call[0][0] for call in mock_logger.info.call_args_list
        ]
        meter2_logged = any("meter2" in call for call in info_calls)
        # Should use .get() which returns None, logged as "meter2=None"
        assert meter2_logged
        
        # Check configuration hint is logged for meter2 with array index
        config_hint_logged = any(
            "disable detection in configuration.yml" in call
            and "modbus.meter[2]" in call
            for call in info_calls
        )
        assert config_hint_logged


class TestDetectMetersExceptionHandling:
    """Tests for _detect_meters exception handling."""

    @pytest.mark.asyncio
    @patch("solaredge2mqtt.services.modbus.logger")
    async def test_detect_meters_skips_meter_on_exception(
        self, mock_logger, mock_service_settings, mock_event_bus
    ):
        """Test that _detect_meters skips meter on exception."""
        with patch(
            "solaredge2mqtt.services.modbus.AsyncModbusTcpClient"
        ):
            modbus = Modbus(mock_service_settings, mock_event_bus)

            unit_key = "leader"
            unit_settings = mock_service_settings.modbus.units[unit_key]
            inverter_raw = {
                "meter0": 172,
                "meter1": 173,
                "c_manufacturer": "SolarEdge",
                "c_model": "SE5000H",
                "c_serialnumber": "12345",
                "c_version": "4.24",
            }

            # Mock read_device_info to raise exception for meter0
            async def mock_read_device_info(
                register_class, uk, identifier, us, offset
            ):
                if identifier == "meter0":
                    raise InvalidRegisterDataException(
                        register_id="c_manufacturer",
                        address=40123,
                        raw_values=[0xC200],
                        original_error=UnicodeDecodeError(
                            "utf-8", b"\xc2", 0, 1, "invalid"
                        ),
                    )

            modbus.read_device_info = AsyncMock(
                side_effect=mock_read_device_info
            )

            # Should not raise exception
            await modbus._detect_meters(
                unit_key, unit_settings, inverter_raw
            )

            # Verify error was logged for meter0
            error_calls = [
                call[0][0] for call in mock_logger.error.call_args_list
            ]
            assert any("meter0" in call for call in error_calls)

    @pytest.mark.asyncio
    async def test_detect_meters_continues_after_exception(
        self, mock_service_settings, mock_event_bus
    ):
        """Test that other meters are still processed after exception."""
        with patch(
            "solaredge2mqtt.services.modbus.AsyncModbusTcpClient"
        ):
            modbus = Modbus(mock_service_settings, mock_event_bus)

            unit_key = "leader"
            unit_settings = mock_service_settings.modbus.units[unit_key]
            inverter_raw = {
                "meter0": 172,
                "meter1": 173,
                "meter2": 174,
                "c_manufacturer": "SolarEdge",
                "c_model": "SE5000H",
                "c_serialnumber": "12345",
                "c_version": "4.24",
            }

            call_count = 0

            async def mock_read_device_info(
                register_class, uk, identifier, us, offset
            ):
                nonlocal call_count
                call_count += 1
                if identifier == "meter0":
                    raise InvalidRegisterDataException(
                        register_id="c_manufacturer",
                        address=40123,
                        raw_values=[0xC200],
                        original_error=UnicodeDecodeError(
                            "utf-8", b"\xc2", 0, 1, "invalid"
                        ),
                    )
                # meter1 and meter2 succeed

            modbus.read_device_info = AsyncMock(
                side_effect=mock_read_device_info
            )

            await modbus._detect_meters(
                unit_key, unit_settings, inverter_raw
            )

            # Should have tried all 3 meters
            assert call_count == 3


class TestDetectBatteries:
    """Tests for _detect_batteries method."""

    @pytest.mark.asyncio
    async def test_detect_batteries_basic(
        self, mock_service_settings, mock_event_bus
    ):
        """Test basic battery detection."""
        with patch(
            "solaredge2mqtt.services.modbus.AsyncModbusTcpClient"
        ):
            modbus = Modbus(mock_service_settings, mock_event_bus)

            unit_key = "leader"
            unit_settings = mock_service_settings.modbus.units[unit_key]
            inverter_raw = {"battery0": 57344}

            modbus.read_device_info = AsyncMock()

            await modbus._detect_batteries(
                unit_key, unit_settings, inverter_raw
            )

            # Should have called read_device_info once for battery0
            assert modbus.read_device_info.call_count == 1


class TestInverterInfoContext:
    """Tests for inverter info context in error messages."""

    @patch("solaredge2mqtt.services.modbus.logger")
    def test_inverter_info_all_fields_present(self, mock_logger):
        """Test inverter info logging with all fields."""
        inverter_raw = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE5000H-US",
            "c_serialnumber": "7F123456",
            "c_version": "0004.0024.0016",
            "meter1": 173,
        }

        exception = InvalidRegisterDataException(
            register_id="c_test",
            address=40000,
            raw_values=[0x0000],
            original_error=UnicodeDecodeError(
                "utf-8", b"\x00", 0, 1, "null byte"
            ),
        )

        Modbus._log_meter_detection_error("meter1", inverter_raw, exception)

        # Find the info call with inverter details
        info_calls = [
            call[0][0] for call in mock_logger.info.call_args_list
        ]

        inverter_context_call = [
            call
            for call in info_calls
            if "Manufacturer=" in call and "Model=" in call
        ]
        assert len(inverter_context_call) > 0

        context = inverter_context_call[0]
        assert "SolarEdge" in context
        assert "SE5000H-US" in context
        assert "7F123456" in context
        assert "0004.0024.0016" in context

    @patch("solaredge2mqtt.services.modbus.logger")
    def test_inverter_info_missing_fields(self, mock_logger):
        """Test inverter info logging with missing fields."""
        inverter_raw = {
            "c_manufacturer": "SolarEdge",
            # c_model missing
            # c_serialnumber missing
            "c_version": "4.24",
            "meter0": 172,
        }

        exception = InvalidRegisterDataException(
            register_id="c_test",
            address=40000,
            raw_values=[0x0000],
            original_error=UnicodeDecodeError(
                "utf-8", b"\x00", 0, 1, "null byte"
            ),
        )

        Modbus._log_meter_detection_error("meter0", inverter_raw, exception)

        # Should still log without crashing
        assert mock_logger.error.call_count == 1
        assert mock_logger.info.call_count >= 2
