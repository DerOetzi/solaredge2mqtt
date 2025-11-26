"""Tests for modbus inverter model module."""


from solaredge2mqtt.services.modbus.models.base import (
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.modbus.models.inverter import (
    ModbusInverter,
    ModbusPowerControl,
)


def make_device_info(with_unit: bool = False) -> ModbusDeviceInfo:
    """Create a ModbusDeviceInfo for testing."""
    data = {
        "c_manufacturer": "SolarEdge",
        "c_model": "SE10K",
        "c_version": "1.0.0",
        "c_serialnumber": "INV12345",
        "c_sunspec_did": 103,
    }
    if with_unit:
        data["unit"] = ModbusUnitInfo(unit=1, key="leader", role=ModbusUnitRole.LEADER)
    return ModbusDeviceInfo(data)


def make_inverter_data(
    status: int = 4,
    with_grid_status: bool = False,
    grid_status: int = 0,
    with_advanced_power: bool = False,
) -> dict:
    """Create inverter data for testing."""
    data = {
        # AC data
        "current": 10.0,
        "current_scale": 0,
        "l1_current": 10.0,
        "l1_voltage": 230.0,
        "voltage_scale": 0,
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
        # DC data
        "current_dc": 10.0,
        "current_dc_scale": 0,
        "voltage_dc": 400.0,
        "voltage_dc_scale": 0,
        "power_dc": 4000.0,
        "power_dc_scale": 0,
        # Other
        "energy_total": 100000.0,
        "energy_total_scale": 0,
        "status": status,
        "temperature": 45.0,
        "temperature_scale": 0,
    }

    if with_grid_status:
        data["grid_status"] = grid_status

    if with_advanced_power:
        data["advanced_power_control_enable"] = True
        data["active_power_limit"] = 100

    return data


class TestModbusInverter:
    """Tests for ModbusInverter class."""

    def test_inverter_creation_valid_status(self):
        """Test inverter creation with valid status."""
        info = make_device_info()
        data = make_inverter_data(status=4)

        inverter = ModbusInverter(info, data)

        assert inverter.status == 4
        assert inverter.status_text == "Inverter is ON and producing power"

    def test_inverter_creation_unknown_status(self):
        """Test inverter creation with unknown status."""
        info = make_device_info()
        data = make_inverter_data(status=999)

        inverter = ModbusInverter(info, data)

        assert inverter.status == 999
        assert inverter.status_text == "Unknown"

    def test_inverter_ac_values(self):
        """Test inverter AC values."""
        info = make_device_info()
        data = make_inverter_data()

        inverter = ModbusInverter(info, data)

        assert inverter.ac.power.actual == 2300.0
        assert inverter.ac.frequency == 50.0

    def test_inverter_dc_values(self):
        """Test inverter DC values."""
        info = make_device_info()
        data = make_inverter_data()

        inverter = ModbusInverter(info, data)

        assert inverter.dc.power == 4000.0
        assert inverter.dc.voltage == 400.0

    def test_inverter_energy_total(self):
        """Test inverter energy total."""
        info = make_device_info()
        data = make_inverter_data()

        inverter = ModbusInverter(info, data)

        assert inverter.energytotal == 100000.0

    def test_inverter_temperature(self):
        """Test inverter temperature."""
        info = make_device_info()
        data = make_inverter_data()

        inverter = ModbusInverter(info, data)

        assert inverter.temperature == 45.0

    def test_inverter_without_grid_status(self):
        """Test inverter without grid status."""
        info = make_device_info()
        data = make_inverter_data(with_grid_status=False)

        inverter = ModbusInverter(info, data)

        assert inverter.grid_status is None

    def test_inverter_with_grid_status_on(self):
        """Test inverter with grid status on (0 = on)."""
        info = make_device_info()
        data = make_inverter_data(with_grid_status=True, grid_status=0)

        inverter = ModbusInverter(info, data)

        # grid_status 0 represents grid ON state (inverted boolean)
        assert inverter.grid_status is True

    def test_inverter_with_grid_status_off(self):
        """Test inverter with grid status off (1 = off)."""
        info = make_device_info()
        data = make_inverter_data(with_grid_status=True, grid_status=1)

        inverter = ModbusInverter(info, data)

        # grid_status 1 represents grid OFF state (inverted boolean)
        assert inverter.grid_status is False

    def test_inverter_without_advanced_power_controls(self):
        """Test inverter without advanced power controls."""
        info = make_device_info()
        data = make_inverter_data(with_advanced_power=False)

        inverter = ModbusInverter(info, data)

        assert inverter.advanced_power_controls is None

    def test_inverter_with_advanced_power_controls(self):
        """Test inverter with advanced power controls."""
        info = make_device_info()
        data = make_inverter_data(with_advanced_power=True)

        inverter = ModbusInverter(info, data)

        assert inverter.advanced_power_controls is not None
        assert inverter.advanced_power_controls.advanced_power_control is True
        assert inverter.advanced_power_controls.active_power_limit == 100

    def test_inverter_homeassistant_device_info(self):
        """Test inverter homeassistant_device_info method."""
        info = make_device_info()
        data = make_inverter_data()

        inverter = ModbusInverter(info, data)
        ha_info = inverter.homeassistant_device_info()

        assert ha_info["name"] == "SolarEdge Inverter"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "SE10K"

    def test_inverter_all_status_values(self):
        """Test inverter with all valid status values."""
        info = make_device_info()
        status_map = {
            1: "Off",
            2: "Sleeping (auto-shutdown) – Night mode",
            3: "Grid Monitoring/wake-up",
            4: "Inverter is ON and producing power",
            5: "Production (curtailed)",
            6: "Shutting down",
            7: "Fault",
            8: "Maintenance/setup",
        }

        for status, expected_text in status_map.items():
            data = make_inverter_data(status=status)
            inverter = ModbusInverter(info, data)
            assert inverter.status_text == expected_text


class TestModbusPowerControl:
    """Tests for ModbusPowerControl class."""

    def test_power_control_creation(self):
        """Test ModbusPowerControl creation."""
        data = {
            "advanced_power_control_enable": True,
            "active_power_limit": 80,
        }

        power_control = ModbusPowerControl(data)

        assert power_control.advanced_power_control is True
        assert power_control.active_power_limit == 80

    def test_power_control_disabled(self):
        """Test ModbusPowerControl when disabled."""
        data = {
            "advanced_power_control_enable": False,
            "active_power_limit": 100,
        }

        power_control = ModbusPowerControl(data)

        assert power_control.advanced_power_control is False
        assert power_control.active_power_limit == 100
