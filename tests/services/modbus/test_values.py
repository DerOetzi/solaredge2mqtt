"""Tests for modbus values models module."""

import sys
import types

import pytest

from solaredge2mqtt.services.modbus.models.values import (
    ModbusAC,
    ModbusACCurrent,
    ModbusACPower,
    ModbusACVoltage,
    ModbusComponentValueGroup,
    ModbusDC,
    ModbusEnergy,
)
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecPayload


def _ensure_influx_point_stub() -> None:
    """Provide a local fallback for influx Point import during test collection."""

    influx_module = sys.modules.setdefault(
        "influxdb_client", types.ModuleType("influxdb_client")
    )
    client_module = sys.modules.setdefault(
        "influxdb_client.client", types.ModuleType("influxdb_client.client")
    )
    write_module = sys.modules.setdefault(
        "influxdb_client.client.write", types.ModuleType("influxdb_client.client.write")
    )

    point_module = types.ModuleType("influxdb_client.client.write.point")

    class Point: ...  # pragma: no cover

    setattr(point_module, "Point", Point)
    sys.modules["influxdb_client.client.write.point"] = point_module

    setattr(influx_module, "client", client_module)
    setattr(client_module, "write", write_module)
    setattr(write_module, "point", point_module)


try:
    from influxdb_client.client.write.point import Point as _InfluxPoint  # noqa: F401
except ImportError:
    _ensure_influx_point_stub()


class TestComponentValueGroup:
    """Tests for ComponentValueGroup class."""

    def test_base_extract_sunspec_payload_returns_none(self):
        """Test abstract base method body executes pass statement."""

        assert ModbusComponentValueGroup.extract_sunspec_payload({}) is None

    def test_scale_value_positive_scale(self):
        """Test scale_value with positive scale."""
        data: SunSpecPayload = {"power": 100, "power_scale": 2}
        result = ModbusComponentValueGroup.scale_value(data, "power")

        assert result == pytest.approx(10000.0)

    def test_scale_value_negative_scale(self):
        """Test scale_value with negative scale."""
        data: SunSpecPayload = {"power": 12345, "power_scale": -2}
        result = ModbusComponentValueGroup.scale_value(data, "power")

        assert result == pytest.approx(123.45)

    def test_scale_value_zero_scale(self):
        """Test scale_value with zero scale."""
        data: SunSpecPayload = {"power": 500, "power_scale": 0}
        result = ModbusComponentValueGroup.scale_value(data, "power")

        assert result == pytest.approx(500.0)

    def test_scale_value_custom_scale_key(self):
        """Test scale_value with custom scale key."""
        data: SunSpecPayload = {"voltage": 2300, "custom_scale": -1}
        result = ModbusComponentValueGroup.scale_value(data, "voltage", "custom_scale")

        assert result == pytest.approx(230.0)

    def test_scale_value_custom_digits(self):
        """Test scale_value with custom digit precision."""
        data: SunSpecPayload = {"power": 333, "power_scale": -2}
        result = ModbusComponentValueGroup.scale_value(data, "power", digits=4)

        assert result == pytest.approx(3.33)

    def test_scale_value_rounding(self):
        """Test scale_value rounds correctly."""
        data: SunSpecPayload = {"power": 12345, "power_scale": -4}
        result = ModbusComponentValueGroup.scale_value(data, "power", digits=2)

        assert result == pytest.approx(1.23)


class TestModbusACCurrent:
    """Tests for ModbusACCurrent class."""

    def test_ac_current_basic(self):
        """Test basic AC current creation."""
        data: SunSpecPayload = {
            "current": 105,
            "current_scale": -1,
        }

        current = ModbusACCurrent.from_sunspec(data)

        assert current.actual == pytest.approx(10.5)
        assert current.l1 is None
        assert current.l2 is None
        assert current.l3 is None

    def test_ac_current_with_phases(self):
        """Test AC current with phase data."""
        data: SunSpecPayload = {
            "current": 300,
            "current_scale": -1,
            "l1_current": 100,
            "l2_current": 100,
            "l3_current": 100,
        }

        current = ModbusACCurrent.from_sunspec(data)

        assert current.actual == pytest.approx(30.0)
        assert current.l1 == pytest.approx(10.0)
        assert current.l2 == pytest.approx(10.0)
        assert current.l3 == pytest.approx(10.0)

    def test_ac_current_with_scale(self):
        """Test AC current with scaling factor."""
        data: SunSpecPayload = {
            "current": 1000,
            "current_scale": -1,
            "l1_current": 333,
            "l2_current": 333,
            "l3_current": 334,
        }

        current = ModbusACCurrent.from_sunspec(data)

        assert current.actual == pytest.approx(100.0)
        assert current.l1 == pytest.approx(33.3)
        assert current.l2 == pytest.approx(33.3)
        assert current.l3 == pytest.approx(33.4)


class TestModbusACVoltage:
    """Tests for ModbusACVoltage class."""

    def test_ac_voltage_empty(self):
        """Test AC voltage with no data."""
        data: SunSpecPayload = {}

        voltage = ModbusACVoltage.from_sunspec(data)

        assert voltage.l1 is None
        assert voltage.l2 is None
        assert voltage.l3 is None
        assert voltage.l1n is None
        assert voltage.l2n is None
        assert voltage.l3n is None

    def test_ac_voltage_with_line_voltages(self):
        """Test AC voltage with line voltages."""
        data: SunSpecPayload = {
            "l1_voltage": 230.0,
            "l2_voltage": 230.0,
            "l3_voltage": 230.0,
            "voltage_scale": 0,
        }

        voltage = ModbusACVoltage.from_sunspec(data)

        assert voltage.l1 == pytest.approx(230.0)
        assert voltage.l2 == pytest.approx(230.0)
        assert voltage.l3 == pytest.approx(230.0)

    def test_ac_voltage_with_neutral_voltages(self):
        """Test AC voltage with neutral voltages."""
        data: SunSpecPayload = {
            "l1n_voltage": 230.0,
            "l2n_voltage": 230.0,
            "l3n_voltage": 230.0,
            "voltage_scale": 0,
        }

        voltage = ModbusACVoltage.from_sunspec(data)

        assert voltage.l1n == pytest.approx(230.0)
        assert voltage.l2n == pytest.approx(230.0)
        assert voltage.l3n == pytest.approx(230.0)

    def test_ac_voltage_with_scale(self):
        """Test AC voltage with scaling factor."""
        data: SunSpecPayload = {
            "l1_voltage": 2300,
            "voltage_scale": -1,
        }

        voltage = ModbusACVoltage.from_sunspec(data)

        assert voltage.l1 == pytest.approx(230.0)


class TestModbusACPower:
    """Tests for ModbusACPower class."""

    def test_ac_power_creation(self):
        """Test AC power creation."""
        data: SunSpecPayload = {
            "power_ac": 5000,
            "power_ac_scale": 0,
            "power_reactive": 100,
            "power_reactive_scale": 0,
            "power_apparent": 5001,
            "power_apparent_scale": 0,
            "power_factor": 9500,
            "power_factor_scale": -4,
        }

        power = ModbusACPower.from_sunspec(data)

        assert power.actual == pytest.approx(5000.0)
        assert power.reactive == pytest.approx(100.0)
        assert power.apparent == pytest.approx(5001.0)
        assert power.factor == pytest.approx(0.95)

    def test_ac_power_with_scale(self):
        """Test AC power with scaling factors."""
        data: SunSpecPayload = {
            "power_ac": 50000,
            "power_ac_scale": -1,
            "power_reactive": 1000,
            "power_reactive_scale": -1,
            "power_apparent": 50010,
            "power_apparent_scale": -1,
            "power_factor": 9800,
            "power_factor_scale": -4,
        }

        power = ModbusACPower.from_sunspec(data)

        assert power.actual == pytest.approx(5000.0)
        assert power.reactive == pytest.approx(100.0)
        assert power.apparent == pytest.approx(5001.0)
        assert power.factor == pytest.approx(0.98)


class TestModbusAC:
    """Tests for ModbusAC class."""

    def test_ac_creation(self):
        """Test AC combined model creation."""
        data: SunSpecPayload = {
            "current": 10.0,
            "current_scale": 0,
            "l1_current": 10.0,
            "power_ac": 2300.0,
            "power_ac_scale": 0,
            "power_reactive": 50.0,
            "power_reactive_scale": 0,
            "power_apparent": 2301.0,
            "power_apparent_scale": 0,
            "power_factor": 0.999,
            "power_factor_scale": 0,
            "frequency": 50.0,
            "frequency_scale": 0,
        }

        ac = ModbusAC.from_sunspec(data)

        assert ac.current.actual == pytest.approx(10.0)
        assert ac.power.actual == pytest.approx(2300.0)
        assert ac.frequency == pytest.approx(50.0)


class TestModbusEnergy:
    """Tests for ModbusEnergy class."""

    def test_energy_creation(self):
        """Test energy model creation."""
        data: SunSpecPayload = {
            "export_energy_active": 100000.0,
            "import_energy_active": 50000.0,
            "energy_active_scale": 0,
        }

        energy = ModbusEnergy.from_sunspec(data)

        assert energy.totalexport == pytest.approx(100000.0)
        assert energy.totalimport == pytest.approx(50000.0)

    def test_energy_with_scale(self):
        """Test energy with scaling factor."""
        data: SunSpecPayload = {
            "export_energy_active": 1000,
            "import_energy_active": 500,
            "energy_active_scale": 3,
        }

        energy = ModbusEnergy.from_sunspec(data)

        assert energy.totalexport == pytest.approx(1000000.0)
        assert energy.totalimport == pytest.approx(500000.0)


class TestModbusDC:
    """Tests for ModbusDC class."""

    def test_dc_creation(self):
        """Test DC model creation."""
        data: SunSpecPayload = {
            "current_dc": 10.0,
            "current_dc_scale": 0,
            "voltage_dc": 400.0,
            "voltage_dc_scale": 0,
            "power_dc": 4000.0,
            "power_dc_scale": 0,
        }

        dc = ModbusDC.from_sunspec(data)

        assert dc.current == pytest.approx(10.0)
        assert dc.voltage == pytest.approx(400.0)
        assert dc.power == pytest.approx(4000.0)

    def test_dc_with_scale(self):
        """Test DC with scaling factors."""
        data: SunSpecPayload = {
            "current_dc": 100,
            "current_dc_scale": -1,
            "voltage_dc": 4000,
            "voltage_dc_scale": -1,
            "power_dc": 40000,
            "power_dc_scale": -1,
        }

        dc = ModbusDC.from_sunspec(data)

        assert dc.current == pytest.approx(10.0)
        assert dc.voltage == pytest.approx(400.0)
        assert dc.power == pytest.approx(4000.0)
