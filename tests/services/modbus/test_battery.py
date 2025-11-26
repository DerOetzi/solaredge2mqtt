"""Tests for modbus battery model module."""

from solaredge2mqtt.services.modbus.models.base import (
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery


def make_device_info(with_unit: bool = False) -> ModbusDeviceInfo:
    """Create a ModbusDeviceInfo for testing."""
    data = {
        "c_manufacturer": "SolarEdge",
        "c_model": "StorEdge",
        "c_version": "1.0.0",
        "c_serialnumber": "BAT123456",
        "c_sunspec_did": 802,
    }
    if with_unit:
        data["unit"] = ModbusUnitInfo(unit=1, key="leader", role=ModbusUnitRole.LEADER)
    return ModbusDeviceInfo(data)


def make_battery_data(
    status: int = 4,
    current: float = 5.5,
    voltage: float = 48.0,
    power: float = 264.0,
    soe: float = 75.5,
    soh: float = 98.2,
) -> dict:
    """Create battery data for testing."""
    return {
        "status": status,
        "instantaneous_current": current,
        "instantaneous_voltage": voltage,
        "instantaneous_power": power,
        "soe": soe,
        "soh": soh,
    }


class TestModbusBattery:
    """Tests for ModbusBattery class."""

    def test_battery_creation_with_valid_status(self):
        """Test battery creation with valid status."""
        info = make_device_info()
        data = make_battery_data(status=4)

        battery = ModbusBattery(info, data)

        assert battery.status == 4
        assert battery.status_text == "Discharge"

    def test_battery_creation_with_unknown_status(self):
        """Test battery creation with unknown status."""
        info = make_device_info()
        data = make_battery_data(status=999)

        battery = ModbusBattery(info, data)

        assert battery.status == 999
        assert battery.status_text == "Unknown"

    def test_battery_values_rounded(self):
        """Test battery values are properly rounded."""
        info = make_device_info()
        data = make_battery_data(
            current=5.556,
            voltage=48.125,
            power=264.999,
            soe=75.555,
            soh=98.224,
        )

        battery = ModbusBattery(info, data)

        assert battery.current == 5.56
        assert battery.voltage == 48.12
        assert battery.power == 265.0
        assert battery.state_of_charge == 75.56
        assert battery.state_of_health == 98.22

    def test_battery_is_valid_with_valid_data(self):
        """Test is_valid returns True with valid data."""
        info = make_device_info()
        data = make_battery_data()

        battery = ModbusBattery(info, data)

        assert battery.is_valid is True

    def test_battery_is_valid_negative_soe(self):
        """Test is_valid returns False with negative state of charge."""
        info = make_device_info()
        data = make_battery_data(soe=-1.0)

        battery = ModbusBattery(info, data)

        assert battery.is_valid is False

    def test_battery_is_valid_negative_soh(self):
        """Test is_valid returns False with negative state of health."""
        info = make_device_info()
        data = make_battery_data(soh=-1.0)

        battery = ModbusBattery(info, data)

        assert battery.is_valid is False

    def test_battery_is_valid_huge_negative_current(self):
        """Test is_valid returns False with huge negative current."""
        info = make_device_info()
        data = make_battery_data(current=-1000001.0)

        battery = ModbusBattery(info, data)

        assert battery.is_valid is False

    def test_battery_prepare_point(self):
        """Test prepare_point creates InfluxDB point."""
        info = make_device_info()
        data = make_battery_data()

        battery = ModbusBattery(info, data)
        point = battery.prepare_point()

        # Convert point to line protocol to verify fields
        line = point.to_line_protocol()
        assert "battery_raw" in line
        assert "current=" in line
        assert "voltage=" in line
        assert "state_of_charge=" in line
        assert "state_of_health=" in line

    def test_battery_prepare_point_custom_measurement(self):
        """Test prepare_point with custom measurement name."""
        info = make_device_info()
        data = make_battery_data()

        battery = ModbusBattery(info, data)
        point = battery.prepare_point("custom_measurement")

        line = point.to_line_protocol()
        assert "custom_measurement" in line

    def test_battery_prepare_point_with_unit(self):
        """Test prepare_point includes unit tag when unit is present."""
        info = make_device_info(with_unit=True)
        data = make_battery_data()

        battery = ModbusBattery(info, data)
        point = battery.prepare_point()

        line = point.to_line_protocol()
        assert "unit=" in line

    def test_battery_homeassistant_device_info(self):
        """Test homeassistant_device_info_with_name method."""
        info = make_device_info()
        data = make_battery_data()

        battery = ModbusBattery(info, data)
        ha_info = battery.homeassistant_device_info_with_name("Battery 1")

        assert ha_info["name"] == "SolarEdge Battery 1"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "StorEdge"

    def test_battery_all_status_values(self):
        """Test battery with all valid status values."""
        info = make_device_info()
        status_map = {
            0: "Off",
            1: "Standby",
            2: "Initializing",
            3: "Charge",
            4: "Discharge",
            5: "Fault",
            6: "Preserve Charge",
            7: "Idle",
            10: "Power Saving",
        }

        for status, expected_text in status_map.items():
            data = make_battery_data(status=status)
            battery = ModbusBattery(info, data)
            assert battery.status_text == expected_text
