"""Tests for modbus events module."""

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent, ModbusWriteEvent
from solaredge2mqtt.services.modbus.sunspec.inverter import SunSpecPowerControlRegister


class TestModbusUnitsReadEvent:
    """Tests for ModbusUnitsReadEvent class."""

    def test_event_is_base_event(self):
        """Test ModbusUnitsReadEvent inherits from BaseEvent."""
        assert issubclass(ModbusUnitsReadEvent, BaseEvent)

    def test_event_units_property(self):
        """Test units property."""
        mock_units = {"leader": "mock_unit"}

        event = ModbusUnitsReadEvent(mock_units)

        assert event.units == mock_units

    def test_event_await_default_false(self):
        """Test AWAIT is False by default."""
        assert ModbusUnitsReadEvent.AWAIT is False


class TestModbusWriteEvent:
    """Tests for ModbusWriteEvent class."""

    def test_event_is_base_event(self):
        """Test ModbusWriteEvent inherits from BaseEvent."""
        assert issubclass(ModbusWriteEvent, BaseEvent)

    def test_event_await_is_true(self):
        """Test AWAIT is True."""
        assert ModbusWriteEvent.AWAIT is True

    def test_event_register_property(self):
        """Test register property."""
        register = SunSpecPowerControlRegister.ACTIVE_POWER_LIMIT

        event = ModbusWriteEvent(register, 100)

        assert event.register == register

    def test_event_payload_property_int(self):
        """Test payload property with int."""
        register = SunSpecPowerControlRegister.ACTIVE_POWER_LIMIT

        event = ModbusWriteEvent(register, 100)

        assert event.payload == 100

    def test_event_payload_property_float(self):
        """Test payload property with float."""
        register = SunSpecPowerControlRegister.COSPHI

        event = ModbusWriteEvent(register, 0.95)

        assert event.payload == 0.95

    def test_event_payload_property_bool(self):
        """Test payload property with bool."""
        register = SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE

        event = ModbusWriteEvent(register, True)

        assert event.payload is True
