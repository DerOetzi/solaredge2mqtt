"""Tests for modbus unit model module."""

from solaredge2mqtt.services.modbus.models.base import (
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.models.meter import ModbusMeter
from solaredge2mqtt.services.modbus.models.unit import ModbusUnit
from solaredge2mqtt.services.modbus.models.values import (
    ModbusAC,
    ModbusACCurrent,
    ModbusACPower,
    ModbusACVoltage,
    ModbusDC,
    ModbusEnergy,
)


def create_device_info() -> ModbusDeviceInfo:
    """Create a test device info."""
    return ModbusDeviceInfo(
        manufacturer="SolarEdge",
        model="SE7600",
        sunspec_type="Inverter",
        version="1.0",
        serialnumber="12345",
    )


def create_unit_info() -> ModbusUnitInfo:
    """Create a test unit info."""
    return ModbusUnitInfo(unit=1, key="leader", role=ModbusUnitRole.LEADER)


def create_inverter() -> ModbusInverter:
    """Create a test inverter."""
    return ModbusInverter(
        info=create_device_info(),
        ac=ModbusAC(
            current=ModbusACCurrent(actual=10.0),
            voltage=ModbusACVoltage(),
            power=ModbusACPower(
                actual=2300.0, reactive=50.0, apparent=2330.0, factor=0.98
            ),
            frequency=50.0,
        ),
        dc=ModbusDC(current=10.0, voltage=350.0, power=3500.0),
        energytotal=1000.0,
        temperature=25.0,
        status_text="OK",
        status=4,
    )


class TestModbusUnit:
    """Tests for ModbusUnit class."""

    def test_modbus_unit_creation(self):
        """Test creating ModbusUnit."""
        inverter = create_inverter()
        unit = ModbusUnit(info=None, inverter=inverter)

        assert unit.inverter == inverter
        assert unit.info is None
        assert unit.meters == {}
        assert unit.batteries == {}

    def test_modbus_unit_with_info(self):
        """Test ModbusUnit with unit info."""
        unit_info = create_unit_info()
        inverter = create_inverter()
        unit = ModbusUnit(info=unit_info, inverter=inverter)

        assert unit.info == unit_info
        assert unit.has_unit_info()

    def test_modbus_unit_without_info(self):
        """Test ModbusUnit without unit info."""
        inverter = create_inverter()
        unit = ModbusUnit(info=None, inverter=inverter)

        assert unit.info is None
        assert not unit.has_unit_info()

    def test_modbus_unit_with_meters(self):
        """Test ModbusUnit with meters."""
        inverter = create_inverter()
        device_info = create_device_info()

        meter = ModbusMeter(
            info=device_info,
            current=ModbusACCurrent(actual=5.0),
            voltage=ModbusACVoltage(),
            power=ModbusACPower(
                actual=1150.0, reactive=25.0, apparent=1165.0, factor=0.98
            ),
            energy=ModbusEnergy(totalexport=500.0, totalimport=100.0),
            frequency=50.0,
        )

        unit = ModbusUnit(info=None, inverter=inverter, meters={"meter1": meter})

        assert "meter1" in unit.meters
        assert unit.meters["meter1"] == meter

    def test_modbus_unit_with_batteries(self):
        """Test ModbusUnit with batteries."""
        inverter = create_inverter()
        device_info = create_device_info()

        battery = ModbusBattery(
            info=device_info,
            status=0,
            status_text="OK",
            current=10.0,
            voltage=48.0,
            power=480.0,
            state_of_charge=80.0,
            state_of_health=100.0,
        )

        unit = ModbusUnit(info=None, inverter=inverter, batteries={"battery1": battery})

        assert "battery1" in unit.batteries
        assert unit.batteries["battery1"] == battery

    def test_modbus_unit_with_meters_and_batteries(self):
        """Test ModbusUnit with both meters and batteries."""
        inverter = create_inverter()
        device_info = create_device_info()

        meter = ModbusMeter(
            info=device_info,
            current=ModbusACCurrent(actual=5.0),
            voltage=ModbusACVoltage(),
            power=ModbusACPower(
                actual=1150.0, reactive=25.0, apparent=1165.0, factor=0.98
            ),
            energy=ModbusEnergy(totalexport=500.0, totalimport=100.0),
            frequency=50.0,
        )

        battery = ModbusBattery(
            info=device_info,
            status=0,
            status_text="OK",
            current=10.0,
            voltage=48.0,
            power=480.0,
            state_of_charge=80.0,
            state_of_health=100.0,
        )

        unit = ModbusUnit(
            info=None,
            inverter=inverter,
            meters={"meter1": meter},
            batteries={"battery1": battery},
        )

        assert len(unit.meters) == 1
        assert len(unit.batteries) == 1

    def test_modbus_unit_empty_meters_default(self):
        """Test ModbusUnit meters default to empty dict."""
        inverter = create_inverter()
        unit = ModbusUnit(info=None, inverter=inverter)

        assert isinstance(unit.meters, dict)
        assert len(unit.meters) == 0

    def test_modbus_unit_empty_batteries_default(self):
        """Test ModbusUnit batteries default to empty dict."""
        inverter = create_inverter()
        unit = ModbusUnit(info=None, inverter=inverter)

        assert isinstance(unit.batteries, dict)
        assert len(unit.batteries) == 0
