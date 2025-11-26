"""Tests for modbus sunspec values module."""

from solaredge2mqtt.services.modbus.sunspec.values import (
    BATTERY_STATUS_MAP,
    C_SUNSPEC_DID_MAP,
    EXPORT_CONTROL_MODE_MAP,
    INVERTER_STATUS_MAP,
    REACTIVE_POWER_CONFIG_MAP,
    SunSpecValueType,
)


class TestConstantMaps:
    """Tests for constant maps."""

    def test_c_sunspec_did_map_inverters(self):
        """Test C_SUNSPEC_DID_MAP for inverters."""
        assert C_SUNSPEC_DID_MAP[101] == "Single Phase Inverter"
        assert C_SUNSPEC_DID_MAP[102] == "Split Phase Inverter"
        assert C_SUNSPEC_DID_MAP[103] == "Three Phase Inverter"

    def test_c_sunspec_did_map_meters(self):
        """Test C_SUNSPEC_DID_MAP for meters."""
        assert C_SUNSPEC_DID_MAP[201] == "Single Phase Meter"
        assert C_SUNSPEC_DID_MAP[202] == "Split Phase Meter"
        assert C_SUNSPEC_DID_MAP[203] == "Wye 3P1N Three Phase Meter"
        assert C_SUNSPEC_DID_MAP[204] == "Delta 3P Three Phase Meter"

    def test_c_sunspec_did_map_batteries(self):
        """Test C_SUNSPEC_DID_MAP for batteries."""
        assert C_SUNSPEC_DID_MAP[802] == "Battery"
        assert C_SUNSPEC_DID_MAP[803] == "Lithium Ion Bank Battery"
        assert C_SUNSPEC_DID_MAP[804] == "Lithium Ion String Battery"

    def test_inverter_status_map(self):
        """Test INVERTER_STATUS_MAP."""
        assert INVERTER_STATUS_MAP[1] == "Off"
        assert INVERTER_STATUS_MAP[4] == "Inverter is ON and producing power"
        assert INVERTER_STATUS_MAP[7] == "Fault"

    def test_battery_status_map(self):
        """Test BATTERY_STATUS_MAP."""
        assert BATTERY_STATUS_MAP[0] == "Off"
        assert BATTERY_STATUS_MAP[3] == "Charge"
        assert BATTERY_STATUS_MAP[4] == "Discharge"
        assert BATTERY_STATUS_MAP[10] == "Power Saving"

    def test_export_control_mode_map(self):
        """Test EXPORT_CONTROL_MODE_MAP."""
        assert EXPORT_CONTROL_MODE_MAP[0] == "Disabled"
        assert EXPORT_CONTROL_MODE_MAP[1] == "Direct Export Limitation"
        assert EXPORT_CONTROL_MODE_MAP[3] == "Production Limitation"

    def test_reactive_power_config_map(self):
        """Test REACTIVE_POWER_CONFIG_MAP."""
        assert REACTIVE_POWER_CONFIG_MAP[0] == "Fixed CosPhi"
        assert REACTIVE_POWER_CONFIG_MAP[4] == "RRCR Mode"


class TestSunSpecValueType:
    """Tests for SunSpecValueType enum."""

    def test_int16_type(self):
        """Test INT16 type."""
        value_type = SunSpecValueType.INT16

        assert value_type.identifier == "int16"
        assert value_type.typed is int
        assert value_type.not_implemented_value == 0x8000

    def test_uint16_type(self):
        """Test UINT16 type."""
        value_type = SunSpecValueType.UINT16

        assert value_type.identifier == "uint16"
        assert value_type.typed is int
        assert value_type.not_implemented_value == 0xFFFF

    def test_int32_type(self):
        """Test INT32 type."""
        value_type = SunSpecValueType.INT32

        assert value_type.identifier == "int32"
        assert value_type.typed is int
        assert value_type.not_implemented_value == 0x80000000

    def test_uint32_type(self):
        """Test UINT32 type."""
        value_type = SunSpecValueType.UINT32

        assert value_type.identifier == "uint32"
        assert value_type.typed is int
        assert value_type.not_implemented_value == 0xFFFFFFFF

    def test_uint64_type(self):
        """Test UINT64 type."""
        value_type = SunSpecValueType.UINT64

        assert value_type.identifier == "uint64"
        assert value_type.typed is int
        assert value_type.not_implemented_value == 0xFFFFFFFFFFFFFFFF

    def test_float32_type(self):
        """Test FLOAT32 type."""
        value_type = SunSpecValueType.FLOAT32

        assert value_type.identifier == "float32"
        assert value_type.typed is float
        assert value_type.not_implemented_value == 0x7FC00000

    def test_string_type(self):
        """Test STRING type."""
        value_type = SunSpecValueType.STRING

        assert value_type.identifier == "string"
        assert value_type.typed is str
        assert value_type.not_implemented_value == ""

    def test_length_property(self):
        """Test length property for value types."""
        # INT16 and UINT16 should have length 1 (1 register)
        assert SunSpecValueType.INT16.length > 0
        assert SunSpecValueType.UINT16.length > 0
        # INT32 and UINT32 should have length 2 (2 registers)
        assert SunSpecValueType.INT32.length > 0
        assert SunSpecValueType.UINT32.length > 0

    def test_data_type_property(self):
        """Test data_type property returns ModbusTcpClient.DATATYPE."""
        value_type = SunSpecValueType.INT16

        # data_type should be set from __modbus_data_type
        assert value_type.data_type is not None
