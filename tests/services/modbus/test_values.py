"""Tests for modbus values models module."""


from solaredge2mqtt.services.modbus.models.values import (
    ModbusAC,
    ModbusACCurrent,
    ModbusACPower,
    ModbusACVoltage,
    ModbusDC,
    ModbusEnergy,
)


class TestModbusACCurrent:
    """Tests for ModbusACCurrent class."""

    def test_ac_current_basic(self):
        """Test basic AC current creation."""
        data = {
            "current": 105,
            "current_scale": -1,
        }

        current = ModbusACCurrent(data)

        assert current.actual == 10.5
        assert current.l1 is None
        assert current.l2 is None
        assert current.l3 is None

    def test_ac_current_with_phases(self):
        """Test AC current with phase data."""
        data = {
            "current": 300,
            "current_scale": -1,
            "l1_current": 100,
            "l2_current": 100,
            "l3_current": 100,
        }

        current = ModbusACCurrent(data)

        assert current.actual == 30.0
        assert current.l1 == 10.0
        assert current.l2 == 10.0
        assert current.l3 == 10.0

    def test_ac_current_with_scale(self):
        """Test AC current with scaling factor."""
        data = {
            "current": 1000,
            "current_scale": -1,
            "l1_current": 333,
            "l2_current": 333,
            "l3_current": 334,
        }

        current = ModbusACCurrent(data)

        assert current.actual == 100.0
        assert current.l1 == 33.3
        assert current.l2 == 33.3
        assert current.l3 == 33.4


class TestModbusACVoltage:
    """Tests for ModbusACVoltage class."""

    def test_ac_voltage_empty(self):
        """Test AC voltage with no data."""
        data = {}

        voltage = ModbusACVoltage(data)

        assert voltage.l1 is None
        assert voltage.l2 is None
        assert voltage.l3 is None
        assert voltage.l1n is None
        assert voltage.l2n is None
        assert voltage.l3n is None

    def test_ac_voltage_with_line_voltages(self):
        """Test AC voltage with line voltages."""
        data = {
            "l1_voltage": 230.0,
            "l2_voltage": 230.0,
            "l3_voltage": 230.0,
            "voltage_scale": 0,
        }

        voltage = ModbusACVoltage(data)

        assert voltage.l1 == 230.0
        assert voltage.l2 == 230.0
        assert voltage.l3 == 230.0

    def test_ac_voltage_with_neutral_voltages(self):
        """Test AC voltage with neutral voltages."""
        data = {
            "l1n_voltage": 230.0,
            "l2n_voltage": 230.0,
            "l3n_voltage": 230.0,
            "voltage_scale": 0,
        }

        voltage = ModbusACVoltage(data)

        assert voltage.l1n == 230.0
        assert voltage.l2n == 230.0
        assert voltage.l3n == 230.0

    def test_ac_voltage_with_scale(self):
        """Test AC voltage with scaling factor."""
        data = {
            "l1_voltage": 2300,
            "voltage_scale": -1,
        }

        voltage = ModbusACVoltage(data)

        assert voltage.l1 == 230.0


class TestModbusACPower:
    """Tests for ModbusACPower class."""

    def test_ac_power_creation(self):
        """Test AC power creation."""
        data = {
            "power_ac": 5000,
            "power_ac_scale": 0,
            "power_reactive": 100,
            "power_reactive_scale": 0,
            "power_apparent": 5001,
            "power_apparent_scale": 0,
            "power_factor": 9500,
            "power_factor_scale": -4,
        }

        power = ModbusACPower(data, "power_ac")

        assert power.actual == 5000.0
        assert power.reactive == 100.0
        assert power.apparent == 5001.0
        # 9500 * 10^-4 = 0.95
        assert power.factor == 0.95

    def test_ac_power_with_scale(self):
        """Test AC power with scaling factors."""
        data = {
            "power_ac": 50000,
            "power_ac_scale": -1,
            "power_reactive": 1000,
            "power_reactive_scale": -1,
            "power_apparent": 50010,
            "power_apparent_scale": -1,
            "power_factor": 9800,
            "power_factor_scale": -4,
        }

        power = ModbusACPower(data, "power_ac")

        assert power.actual == 5000.0
        assert power.reactive == 100.0
        assert power.apparent == 5001.0
        # 9800 * 10^-4 = 0.98
        assert power.factor == 0.98


class TestModbusAC:
    """Tests for ModbusAC class."""

    def test_ac_creation(self):
        """Test AC combined model creation."""
        data = {
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

        ac = ModbusAC(data)

        assert ac.current.actual == 10.0
        assert ac.power.actual == 2300.0
        assert ac.frequency == 50.0


class TestModbusEnergy:
    """Tests for ModbusEnergy class."""

    def test_energy_creation(self):
        """Test energy model creation."""
        data = {
            "export_energy_active": 100000.0,
            "import_energy_active": 50000.0,
            "energy_active_scale": 0,
        }

        energy = ModbusEnergy(data)

        assert energy.totalexport == 100000.0
        assert energy.totalimport == 50000.0

    def test_energy_with_scale(self):
        """Test energy with scaling factor."""
        data = {
            "export_energy_active": 1000,
            "import_energy_active": 500,
            "energy_active_scale": 3,
        }

        energy = ModbusEnergy(data)

        assert energy.totalexport == 1000000.0
        assert energy.totalimport == 500000.0


class TestModbusDC:
    """Tests for ModbusDC class."""

    def test_dc_creation(self):
        """Test DC model creation."""
        data = {
            "current_dc": 10.0,
            "current_dc_scale": 0,
            "voltage_dc": 400.0,
            "voltage_dc_scale": 0,
            "power_dc": 4000.0,
            "power_dc_scale": 0,
        }

        dc = ModbusDC(data)

        assert dc.current == 10.0
        assert dc.voltage == 400.0
        assert dc.power == 4000.0

    def test_dc_with_scale(self):
        """Test DC with scaling factors."""
        data = {
            "current_dc": 100,
            "current_dc_scale": -1,
            "voltage_dc": 4000,
            "voltage_dc_scale": -1,
            "power_dc": 40000,
            "power_dc_scale": -1,
        }

        dc = ModbusDC(data)

        assert dc.current == 10.0
        assert dc.voltage == 400.0
        assert dc.power == 4000.0
