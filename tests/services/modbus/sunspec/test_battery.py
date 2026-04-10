"""Tests for modbus sunspec battery register definitions."""

from solaredge2mqtt.services.modbus.sunspec.battery import SunSpecBatteryRegister


class TestSunSpecBatteryRegister:
    """Tests for SunSpecBatteryRegister."""

    def test_wordorder_is_little_endian(self):
        """Battery registers must use little-endian word order."""

        assert SunSpecBatteryRegister.wordorder() == "little"
