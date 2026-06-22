"""Tests for monitoring models module."""

from datetime import datetime, timezone

import pytest

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.monitoring.models import (
    EVCharger,
    EVChargerInfo,
    LogicalInfo,
    LogicalInverter,
    LogicalModule,
    LogicalString,
)

SAMPLE_INFO = EVChargerInfo(
    manufacturer="Keba AG",
    model="P30",
    version="1.2.3",
    serialnumber="SN123456",
    name="EV Charger",
    reporter_id=12345,
)


def make_charger_device(**overrides) -> dict:
    base = {
        "manufacturer": "Keba AG",
        "model": "P30",
        "swVersion": "1.2.3",
        "serialNumber": "SN123456",
        "name": "EV Charger",
        "reporterId": 12345,
        "chargerStatus": "READY",
        "connectionStatus": "CONNECTED",
        "sessionActive": True,
        "sessionEnergy": 5000,
        "ratedPower": 11000.0,
        "actionOperationDetails": [],
    }
    base.update(overrides)
    return base


def make_evcharger(
    info: EVChargerInfo = SAMPLE_INFO,
    charge_level: int = 0,
    charger_status: str = "READY",
    connected: bool = True,
    session_energy: int = 5000,
    rated_power: float = 11000.0,
) -> EVCharger:
    return EVCharger(
        info=info,
        charge_level=charge_level,
        charger_status=charger_status,
        connected=connected,
        session_energy=session_energy,
        rated_power=rated_power,
    )


class TestEVChargerInfo:
    """Tests for EVChargerInfo model."""

    def test_from_device(self):
        device = {
            "manufacturer": "Keba AG",
            "model": "P30",
            "swVersion": "1.2.3",
            "serialNumber": "SN123456",
            "name": "EV Charger",
            "reporterId": 385723326674278,
        }
        info = EVChargerInfo.from_device(device)
        assert info.manufacturer == "Keba AG"
        assert info.model == "P30"
        assert info.version == "1.2.3"
        assert info.serialnumber == "SN123456"
        assert info.name == "EV Charger"
        assert info.reporter_id == 385723326674278

    def test_from_device_missing_key_raises(self):
        with pytest.raises(InvalidDataException):
            EVChargerInfo.from_device({"manufacturer": "X"})

    def test_homeassistant_device_info(self):
        info = EVChargerInfo(
            manufacturer="Keba AG",
            model="P30",
            version="1.2.3",
            serialnumber="SN123456",
            name="EV Charger",
            reporter_id=12345,
        )
        result = info.homeassistant_device_info()
        assert result == {
            "name": "EV Charger",
            "manufacturer": "Keba AG",
            "model": "P30",
            "sw_version": "1.2.3",
            "serial_number": "SN123456",
        }


class TestEVCharger:
    """Tests for EVCharger component model."""

    def test_from_device_action_op_off_gives_charge_level_100(self):
        device = make_charger_device(
            actionOperationDetails=[{"actionOp": "OFF", "actionText": "STOP_CHARGING"}]
        )
        charger = EVCharger.from_device(device)
        assert charger.charge_level == 100

    def test_from_device_action_op_on_gives_charge_level_0(self):
        device = make_charger_device(
            actionOperationDetails=[{"actionOp": "ON", "actionText": "START_CHARGING"}]
        )
        charger = EVCharger.from_device(device)
        assert charger.charge_level == 0

    def test_from_device_no_action_op_details_gives_charge_level_0(self):
        device = make_charger_device(actionOperationDetails=[])
        charger = EVCharger.from_device(device)
        assert charger.charge_level == 0

    def test_from_device_connected_via_connection_status(self):
        device = make_charger_device(connectionStatus="CONNECTED", sessionActive=False)
        charger = EVCharger.from_device(device)
        assert charger.connected is True

    def test_from_device_connected_via_session_active(self):
        device = make_charger_device(
            connectionStatus="DISCONNECTED", sessionActive=True
        )
        charger = EVCharger.from_device(device)
        assert charger.connected is True

    def test_from_device_not_connected(self):
        device = make_charger_device(
            connectionStatus="DISCONNECTED", sessionActive=False
        )
        charger = EVCharger.from_device(device)
        assert charger.connected is False

    def test_from_device_missing_key_raises(self):
        device = {
            "manufacturer": "Keba AG",
            "model": "P30",
            "swVersion": "1.2.3",
            "serialNumber": "SN123456",
            "name": "EV Charger",
            "reporterId": 12345,
        }
        with pytest.raises(InvalidDataException):
            EVCharger.from_device(device)

    def test_mqtt_topic(self):
        charger = make_evcharger()
        assert charger.mqtt_topic() == "monitoring/evcharger/12345"

    def test_mqtt_chargelevel_topic(self):
        charger = make_evcharger()
        assert (
            charger.mqtt_chargelevel_topic()
            == "monitoring/evcharger/12345/charge_level"
        )

    def test_homeassistant_device_info_delegates_to_info(self):
        charger = make_evcharger()
        assert (
            charger.homeassistant_device_info()
            == SAMPLE_INFO.homeassistant_device_info()
        )

    def test_serialize_connected_true(self):
        charger = make_evcharger(connected=True)
        assert charger.serialize_connected(True) == "true"

    def test_serialize_connected_false(self):
        charger = make_evcharger(connected=False)
        assert charger.serialize_connected(False) == "false"

    def test_connected_serialized_as_string_in_json(self):
        charger = make_evcharger(connected=True)
        dumped = charger.model_dump()
        assert dumped["connected"] == "true"


class TestLogicalInfo:
    """Tests for LogicalInfo class."""

    def test_logical_info_creation(self):
        """Test LogicalInfo creation with all fields."""
        info = LogicalInfo(
            identifier="123",
            serialnumber="SN12345",
            name="Module 1",
            type="PANEL",
        )

        assert info.identifier == "123"
        assert info.serialnumber == "SN12345"
        assert info.name == "Module 1"
        assert info.type == "PANEL"

    def test_logical_info_with_none_serialnumber(self):
        """Test LogicalInfo with None serialnumber."""
        info = LogicalInfo(
            identifier="456",
            serialnumber=None,
            name="String A",
            type="STRING",
        )

        assert info.serialnumber is None

    def test_logical_info_map_method(self):
        """Test LogicalInfo.map static method."""
        data = {
            "id": 789,
            "serialNumber": "SN789",
            "name": "Inverter 1",
            "type": "INVERTER",
        }

        result = LogicalInfo.map(data)

        assert result["identifier"] == "789"
        assert result["serialnumber"] == "SN789"
        assert result["name"] == "Inverter 1"
        assert result["type"] == "INVERTER"

    def test_logical_info_map_method_string_id(self):
        """Test LogicalInfo.map converts numeric id to string."""
        data = {
            "id": 12345,
            "serialNumber": "SN001",
            "name": "Test",
            "type": "MODULE",
        }

        result = LogicalInfo.map(data)

        assert isinstance(result["identifier"], str)
        assert result["identifier"] == "12345"

    def test_logical_info_map_invalid_input_raises(self):
        """Test LogicalInfo.map raises on non-dict data."""
        with pytest.raises(InvalidDataException):
            LogicalInfo.map("invalid")


class TestLogicalInverter:
    """Tests for LogicalInverter class."""

    def test_logical_inverter_creation(self):
        """Test LogicalInverter creation."""
        info = LogicalInfo(
            identifier="1",
            serialnumber="INV001",
            name="Inverter 1",
            type="INVERTER",
        )
        inverter = LogicalInverter(info=info, energy=5000.0)

        assert inverter.info.identifier == "1"
        assert inverter.energy == pytest.approx(5000.0)
        assert inverter.strings == []

    def test_logical_inverter_with_none_energy(self):
        """Test LogicalInverter with None energy."""
        info = LogicalInfo(
            identifier="1",
            serialnumber="INV001",
            name="Inverter 1",
            type="INVERTER",
        )
        inverter = LogicalInverter(info=info, energy=None)

        assert inverter.energy is None

    def test_logical_inverter_default_strings(self):
        """Test LogicalInverter default strings is empty list."""
        info = LogicalInfo(
            identifier="1",
            serialnumber="INV001",
            name="Inverter 1",
            type="INVERTER",
        )
        inverter = LogicalInverter(info=info, energy=1000.0)

        assert isinstance(inverter.strings, list)
        assert len(inverter.strings) == 0


class TestLogicalString:
    """Tests for LogicalString class."""

    def test_logical_string_creation(self):
        """Test LogicalString creation."""
        info = LogicalInfo(
            identifier="2",
            serialnumber="STR001",
            name="String A",
            type="STRING",
        )
        string = LogicalString(info=info, energy=2500.0)

        assert string.info.identifier == "2"
        assert string.energy == pytest.approx(2500.0)
        assert string.modules == []

    def test_logical_string_with_none_energy(self):
        """Test LogicalString with None energy."""
        info = LogicalInfo(
            identifier="2",
            serialnumber="STR001",
            name="String A",
            type="STRING",
        )
        string = LogicalString(info=info, energy=None)

        assert string.energy is None

    def test_logical_string_default_modules(self):
        """Test LogicalString default modules is empty list."""
        info = LogicalInfo(
            identifier="2",
            serialnumber="STR001",
            name="String A",
            type="STRING",
        )
        string = LogicalString(info=info, energy=500.0)

        assert isinstance(string.modules, list)
        assert len(string.modules) == 0


class TestLogicalModule:
    """Tests for LogicalModule class."""

    def test_logical_module_creation(self):
        """Test LogicalModule creation."""
        info = LogicalInfo(
            identifier="3",
            serialnumber="MOD001",
            name="Panel 1",
            type="PANEL",
        )
        module = LogicalModule(info=info, energy=100.0)

        assert module.info.identifier == "3"
        assert module.energy == pytest.approx(100.0)
        assert module.power is None

    def test_logical_module_with_none_energy(self):
        """Test LogicalModule with None energy."""
        info = LogicalInfo(
            identifier="3",
            serialnumber="MOD001",
            name="Panel 1",
            type="PANEL",
        )
        module = LogicalModule(info=info, energy=None)

        assert module.energy is None

    def test_logical_module_with_power_data(self):
        """Test LogicalModule with power data."""
        info = LogicalInfo(
            identifier="3",
            serialnumber="MOD001",
            name="Panel 1",
            type="PANEL",
        )
        power_data = {
            datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc): 150.5,
            datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc): 145.2,
        }
        module = LogicalModule(info=info, energy=100.0, power=power_data)

        assert module.power is not None
        assert len(module.power) == 2

    def test_logical_module_power_today_computed_field_none(self):
        """Test power_today returns None when power is None."""
        info = LogicalInfo(
            identifier="3",
            serialnumber="MOD001",
            name="Panel 1",
            type="PANEL",
        )
        module = LogicalModule(info=info, energy=100.0)

        assert module.power_today is None

    def test_logical_module_power_today_computed_field_with_data(self):
        """Test power_today transforms datetime keys to HH:MM format."""
        info = LogicalInfo(
            identifier="3",
            serialnumber="MOD001",
            name="Panel 1",
            type="PANEL",
        )
        power_data = {
            datetime(2024, 6, 15, 12, 30, tzinfo=timezone.utc): 150.5,
            datetime(2024, 6, 15, 13, 45, tzinfo=timezone.utc): 145.2,
        }
        module = LogicalModule(info=info, energy=100.0, power=power_data)

        power_today = module.power_today

        assert power_today is not None
        assert "12:30" in power_today
        assert "13:45" in power_today
        assert power_today["12:30"] == pytest.approx(150.5)
        assert power_today["13:45"] == pytest.approx(145.2)

    def test_logical_module_model_dump_includes_power_today(self):
        """Test model dump includes power_today computed field."""
        info = LogicalInfo(
            identifier="3",
            serialnumber="MOD001",
            name="Panel 1",
            type="PANEL",
        )
        power_data = {
            datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc): 150.0,
        }
        module = LogicalModule(info=info, energy=100.0, power=power_data)

        dump = module.model_dump()

        assert "power_today" in dump
        assert dump["power_today"]["12:00"] == pytest.approx(150.0)
