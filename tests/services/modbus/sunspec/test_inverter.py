"""Tests for modbus sunspec inverter module."""

from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecGridStatusRegister,
    SunSpecInverterInfoRegister,
    SunSpecInverterRegister,
    SunSpecPowerControlRegister,
    SunSpecSiteLimitRegister,
)
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecValueType


class TestSunSpecInverterInfoRegister:
    """Tests for SunSpecInverterInfoRegister class."""

    def test_c_manufacturer_register(self):
        """Test C_MANUFACTURER register properties."""
        reg = SunSpecInverterInfoRegister.C_MANUFACTURER

        assert reg.identifier == "c_manufacturer"
        assert reg.address == 40004
        assert reg.value_type == SunSpecValueType.STRING
        assert reg.required is True
        assert reg.length == 16

    def test_c_model_register(self):
        """Test C_MODEL register properties."""
        reg = SunSpecInverterInfoRegister.C_MODEL

        assert reg.identifier == "c_model"
        assert reg.address == 40020
        assert reg.value_type == SunSpecValueType.STRING
        assert reg.required is True

    def test_c_serialnumber_register(self):
        """Test C_SERIALNUMBER register properties."""
        reg = SunSpecInverterInfoRegister.C_SERIALNUMBER

        assert reg.identifier == "c_serialnumber"
        assert reg.address == 40052
        assert reg.value_type == SunSpecValueType.STRING
        assert reg.required is True

    def test_c_sunspec_did_register(self):
        """Test C_SUNSPEC_DID register properties."""
        reg = SunSpecInverterInfoRegister.C_SUNSPEC_DID

        assert reg.identifier == "c_sunspec_did"
        assert reg.address == 40069
        assert reg.value_type == SunSpecValueType.UINT16
        assert reg.required is True

    def test_meter_registers(self):
        """Test METER0-2 register properties."""
        assert SunSpecInverterInfoRegister.METER0.identifier == "meter0"
        assert SunSpecInverterInfoRegister.METER0.required is True

        assert SunSpecInverterInfoRegister.METER1.identifier == "meter1"
        assert SunSpecInverterInfoRegister.METER1.required is True

        assert SunSpecInverterInfoRegister.METER2.identifier == "meter2"
        assert SunSpecInverterInfoRegister.METER2.required is True

    def test_battery_registers(self):
        """Test BATTERY0-1 register properties."""
        assert SunSpecInverterInfoRegister.BATTERY0.identifier == "battery0"
        assert SunSpecInverterInfoRegister.BATTERY0.required is True

        assert SunSpecInverterInfoRegister.BATTERY1.identifier == "battery1"
        assert SunSpecInverterInfoRegister.BATTERY1.required is True


class TestSunSpecInverterRegister:
    """Tests for SunSpecInverterRegister class."""

    def test_current_register(self):
        """Test CURRENT register properties."""
        reg = SunSpecInverterRegister.CURRENT

        assert reg.identifier == "current"
        assert reg.address == 40071
        assert reg.value_type == SunSpecValueType.UINT16
        assert reg.required is True

    def test_power_ac_register(self):
        """Test POWER_AC register properties."""
        reg = SunSpecInverterRegister.POWER_AC

        assert reg.identifier == "power_ac"
        assert reg.address == 40083
        assert reg.value_type == SunSpecValueType.INT16
        assert reg.required is True

    def test_energy_total_register(self):
        """Test ENERGY_TOTAL register properties."""
        reg = SunSpecInverterRegister.ENERGY_TOTAL

        assert reg.identifier == "energy_total"
        assert reg.address == 40093
        assert reg.value_type == SunSpecValueType.UINT32
        assert reg.required is True
        assert reg.length == 2  # UINT32 is 2 registers

    def test_status_register(self):
        """Test STATUS register properties."""
        reg = SunSpecInverterRegister.STATUS

        assert reg.identifier == "status"
        assert reg.address == 40107
        assert reg.value_type == SunSpecValueType.UINT16
        assert reg.required is True

    def test_temperature_register(self):
        """Test TEMPERATURE register properties."""
        reg = SunSpecInverterRegister.TEMPERATURE

        assert reg.identifier == "temperature"
        assert reg.address == 40103
        assert reg.required is True

    def test_power_dc_register(self):
        """Test POWER_DC register properties."""
        reg = SunSpecInverterRegister.POWER_DC

        assert reg.identifier == "power_dc"
        assert reg.address == 40100
        assert reg.required is True


class TestSunSpecGridStatusRegister:
    """Tests for SunSpecGridStatusRegister class."""

    def test_grid_status_register(self):
        """Test GRID_STATUS register properties."""
        reg = SunSpecGridStatusRegister.GRID_STATUS

        assert reg.identifier == "grid_status"
        assert reg.address == 40113
        assert reg.value_type == SunSpecValueType.UINT32
        assert reg.required is True


class TestSunSpecPowerControlRegister:
    """Tests for SunSpecPowerControlRegister class."""

    def test_rrcr_state_register(self):
        """Test RRCR_STATE register properties."""
        reg = SunSpecPowerControlRegister.RRCR_STATE

        assert reg.identifier == "rrcr_state"
        assert reg.address == 61440
        assert reg.value_type == SunSpecValueType.UINT16
        assert reg.required is True

    def test_active_power_limit_register(self):
        """Test ACTIVE_POWER_LIMIT register properties."""
        reg = SunSpecPowerControlRegister.ACTIVE_POWER_LIMIT

        assert reg.identifier == "active_power_limit"
        assert reg.address == 61441
        assert reg.required is True

    def test_commit_power_control_settings_register(self):
        """Test COMMIT_POWER_CONTROL_SETTINGS register properties."""
        reg = SunSpecPowerControlRegister.COMMIT_POWER_CONTROL_SETTINGS

        assert reg.identifier == "commit_power_control_settings"
        assert reg.address == 61696
        assert reg.required is True

    def test_advanced_power_control_enable_register(self):
        """Test ADVANCED_POWER_CONTROL_ENABLE register properties."""
        reg = SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE

        assert reg.identifier == "advanced_power_control_enable"
        assert reg.address == 61762
        assert reg.value_type == SunSpecValueType.INT32
        assert reg.required is True

    def test_reactive_power_config_register(self):
        """Test REACTIVE_POWER_CONFIG register properties."""
        reg = SunSpecPowerControlRegister.REACTIVE_POWER_CONFIG

        assert reg.identifier == "reactive_power_config"
        assert reg.address == 61700
        assert reg.value_type == SunSpecValueType.INT32
        assert reg.required is True

    def test_wordorder_little_endian(self):
        """Test wordorder returns little for power control registers."""
        assert SunSpecPowerControlRegister.wordorder() == "little"

    def test_decode_response_advanced_power_control_enable_true(self):
        """Test decode_response converts 1 to True for advanced power control."""
        reg = SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE
        data = {}

        # INT32 little endian: value 1 is [1, 0]
        result = reg.decode_response([1, 0], data)

        assert result["advanced_power_control_enable"] is True

    def test_decode_response_advanced_power_control_enable_false(self):
        """Test decode_response converts non-1 to False for advanced power control."""
        reg = SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE
        data = {}

        result = reg.decode_response([0, 0], data)

        assert result["advanced_power_control_enable"] is False


class TestSunSpecSiteLimitRegister:
    """Tests for SunSpecSiteLimitRegister class."""

    def test_export_control_mode_register(self):
        """Test EXPORT_CONTROL_MODE register properties."""
        reg = SunSpecSiteLimitRegister.EXPORT_CONTROL_MODE

        assert reg.identifier == "export_control_mode"
        assert reg.address == 57344
        assert reg.value_type == SunSpecValueType.UINT16
        assert reg.required is True

    def test_export_control_site_limit_register(self):
        """Test EXPORT_CONTROL_SITE_LIMIT register properties."""
        reg = SunSpecSiteLimitRegister.EXPORT_CONTROL_SITE_LIMIT

        assert reg.identifier == "export_control_site_limit"
        assert reg.address == 57346
        assert reg.value_type == SunSpecValueType.FLOAT32
        assert reg.required is True

    def test_wordorder_little_endian(self):
        """Test wordorder returns little for site limit registers."""
        assert SunSpecSiteLimitRegister.wordorder() == "little"
