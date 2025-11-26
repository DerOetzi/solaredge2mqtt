"""Tests for modbus meter model module."""

from solaredge2mqtt.services.modbus.models.base import (
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.modbus.models.meter import ModbusMeter


def make_device_info(with_unit: bool = False) -> ModbusDeviceInfo:
    """Create a ModbusDeviceInfo for testing."""
    data = {
        "c_manufacturer": "SolarEdge",
        "c_model": "SE-WNC-3Y-400-MB-K1",
        "c_version": "1.0.0",
        "c_serialnumber": "MTR123456",
        "c_sunspec_did": 203,
    }
    if with_unit:
        data["unit"] = ModbusUnitInfo(unit=1, key="leader", role=ModbusUnitRole.LEADER)
    return ModbusDeviceInfo(data)


def make_meter_data() -> dict:
    """Create meter data for testing."""
    return {
        # Current data
        "current": 300,
        "current_scale": -1,
        "l1_current": 100,
        "l2_current": 100,
        "l3_current": 100,
        # Voltage data
        "l1_voltage": 2300,
        "l2_voltage": 2300,
        "l3_voltage": 2300,
        "voltage_scale": -1,
        "l1n_voltage": 2300,
        "l2n_voltage": 2300,
        "l3n_voltage": 2300,
        # Power data
        "power": 6900,
        "power_scale": 0,
        "power_reactive": 100,
        "power_reactive_scale": 0,
        "power_apparent": 6901,
        "power_apparent_scale": 0,
        "power_factor": 9500,
        "power_factor_scale": -4,
        # Energy data
        "export_energy_active": 100000,
        "import_energy_active": 50000,
        "energy_active_scale": 0,
        # Frequency
        "frequency": 500,
        "frequency_scale": -1,
    }


class TestModbusMeter:
    """Tests for ModbusMeter class."""

    def test_meter_creation(self):
        """Test meter creation."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter(info, data)

        assert meter.current.actual == 30.0
        assert meter.voltage.l1 == 230.0
        assert meter.power.actual == 6900.0
        assert meter.energy.totalexport == 100000.0
        assert meter.energy.totalimport == 50000.0
        assert meter.frequency == 50.0

    def test_meter_component_constant(self):
        """Test meter COMPONENT constant."""
        assert ModbusMeter.COMPONENT == "meter"

    def test_meter_current_phases(self):
        """Test meter current with phases."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter(info, data)

        assert meter.current.l1 == 10.0
        assert meter.current.l2 == 10.0
        assert meter.current.l3 == 10.0

    def test_meter_voltage_phases(self):
        """Test meter voltage with phases."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter(info, data)

        assert meter.voltage.l1 == 230.0
        assert meter.voltage.l2 == 230.0
        assert meter.voltage.l3 == 230.0
        assert meter.voltage.l1n == 230.0
        assert meter.voltage.l2n == 230.0
        assert meter.voltage.l3n == 230.0

    def test_meter_power_values(self):
        """Test meter power values."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter(info, data)

        assert meter.power.actual == 6900.0
        assert meter.power.reactive == 100.0
        assert meter.power.apparent == 6901.0
        # 9500 * 10^-4 = 0.95
        assert meter.power.factor == 0.95

    def test_meter_homeassistant_device_info_with_name(self):
        """Test homeassistant_device_info_with_name method."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter(info, data)
        ha_info = meter.homeassistant_device_info_with_name("Meter 1")

        assert ha_info["name"] == "SolarEdge Meter 1"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "SE-WNC-3Y-400-MB-K1"

    def test_meter_with_unit(self):
        """Test meter with unit info."""
        info = make_device_info(with_unit=True)
        data = make_meter_data()

        meter = ModbusMeter(info, data)

        assert meter.info.has_unit is True
        assert meter.info.unit.key == "leader"
