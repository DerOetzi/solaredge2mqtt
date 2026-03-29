"""Tests for modbus meter model module."""

import pytest

from solaredge2mqtt.services.modbus.models.base import (
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.modbus.models.meter import ModbusMeter
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecPayload


def make_device_info(with_unit: bool = False) -> ModbusDeviceInfo:
    """Create a ModbusDeviceInfo for testing."""
    data: SunSpecPayload = {
        "c_manufacturer": "SolarEdge",
        "c_model": "SE-WNC-3Y-400-MB-K1",
        "c_version": "1.0.0",
        "c_serialnumber": "MTR123456",
        "c_sunspec_did": 203,
    }

    return ModbusDeviceInfo.from_sunspec(
        data,
        ModbusUnitInfo(unit=1, key="leader", role=ModbusUnitRole.LEADER)
        if with_unit
        else None,
    )


def make_meter_data() -> SunSpecPayload:
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

        meter = ModbusMeter.from_sunspec(info, data)

        assert meter.current.actual == pytest.approx(30.0)
        assert meter.voltage.l1 == pytest.approx(230.0)
        assert meter.power.actual == pytest.approx(6900.0)
        assert meter.energy.totalexport == pytest.approx(100000.0)
        assert meter.energy.totalimport == pytest.approx(50000.0)
        assert meter.frequency == pytest.approx(50.0)

    def test_meter_component_constant(self):
        """Test meter COMPONENT constant."""
        assert ModbusMeter.COMPONENT == "meter"

    def test_meter_current_phases(self):
        """Test meter current with phases."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter.from_sunspec(info, data)

        assert meter.current.l1 == pytest.approx(10.0)
        assert meter.current.l2 == pytest.approx(10.0)
        assert meter.current.l3 == pytest.approx(10.0)

    def test_meter_voltage_phases(self):
        """Test meter voltage with phases."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter.from_sunspec(info, data)

        assert meter.voltage.l1 == pytest.approx(230.0)
        assert meter.voltage.l2 == pytest.approx(230.0)
        assert meter.voltage.l3 == pytest.approx(230.0)
        assert meter.voltage.l1n == pytest.approx(230.0)
        assert meter.voltage.l2n == pytest.approx(230.0)
        assert meter.voltage.l3n == pytest.approx(230.0)

    def test_meter_power_values(self):
        """Test meter power values."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter.from_sunspec(info, data)

        assert meter.power.actual == pytest.approx(6900.0)
        assert meter.power.reactive == pytest.approx(100.0)
        assert meter.power.apparent == pytest.approx(6901.0)
        assert meter.power.factor == pytest.approx(0.95)

    def test_meter_homeassistant_device_info_with_name(self):
        """Test homeassistant_device_info_with_name method."""
        info = make_device_info()
        data = make_meter_data()

        meter = ModbusMeter.from_sunspec(info, data)
        ha_info = meter.homeassistant_device_info_with_name("Meter 1")

        assert ha_info["name"] == "SolarEdge Meter 1"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "SE-WNC-3Y-400-MB-K1"

    def test_meter_with_unit(self):
        """Test meter with unit info."""
        info = make_device_info(with_unit=True)
        data = make_meter_data()

        meter = ModbusMeter.from_sunspec(info, data)

        assert meter.info.unit is not None
        assert meter.info.unit.key == "leader"
