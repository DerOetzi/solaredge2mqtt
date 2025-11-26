"""Tests for monitoring models module."""

from datetime import datetime, timezone

from solaredge2mqtt.services.monitoring.models import (
    LogicalInfo,
    LogicalInverter,
    LogicalModule,
    LogicalString,
)


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
        assert inverter.energy == 5000.0
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
        assert string.energy == 2500.0
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
        assert module.energy == 100.0
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
        assert power_today["12:30"] == 150.5
        assert power_today["13:45"] == 145.2

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
        assert dump["power_today"]["12:00"] == 150.0
