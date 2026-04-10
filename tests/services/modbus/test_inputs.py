"""Tests for modbus inputs model module."""

import pytest
from pydantic import ValidationError

from solaredge2mqtt.services.modbus.models.inputs import (
    ModbusActivePowerLimitInput,
    ModbusPowerControlInput,
)


class TestModbusActivePowerLimitInput:
    """Tests for ModbusActivePowerLimitInput class."""

    def test_valid_limit_0(self):
        """Test valid limit of 0."""
        input_model = ModbusActivePowerLimitInput(limit=0)

        assert input_model.limit == 0

    def test_valid_limit_50(self):
        """Test valid limit of 50."""
        input_model = ModbusActivePowerLimitInput(limit=50)

        assert input_model.limit == 50

    def test_valid_limit_100(self):
        """Test valid limit of 100."""
        input_model = ModbusActivePowerLimitInput(limit=100)

        assert input_model.limit == 100

    def test_invalid_limit_negative(self):
        """Test invalid negative limit."""
        with pytest.raises(ValidationError):
            ModbusActivePowerLimitInput(limit=-1)

    def test_invalid_limit_above_100(self):
        """Test invalid limit above 100."""
        with pytest.raises(ValidationError):
            ModbusActivePowerLimitInput(limit=101)

    def test_valid_limit_boundary_min(self):
        """Test boundary value at minimum."""
        input_model = ModbusActivePowerLimitInput(limit=0)

        assert input_model.limit == 0

    def test_valid_limit_boundary_max(self):
        """Test boundary value at maximum."""
        input_model = ModbusActivePowerLimitInput(limit=100)

        assert input_model.limit == 100


class TestModbusPowerControlInput:
    """Tests for ModbusPowerControlInput enum."""

    def test_active_power_limit_has_attribute(self):
        """Test ACTIVE_POWER_LIMIT exists."""
        assert hasattr(ModbusPowerControlInput, "ACTIVE_POWER_LIMIT")

    def test_active_power_limit_key(self):
        """Test ACTIVE_POWER_LIMIT key."""
        assert ModbusPowerControlInput.ACTIVE_POWER_LIMIT.key == "active_power_limit"

    def test_active_power_limit_input_model(self):
        """Test ACTIVE_POWER_LIMIT input_model."""
        assert (
            ModbusPowerControlInput.ACTIVE_POWER_LIMIT.input_model
            == ModbusActivePowerLimitInput
        )

    def test_active_power_limit_from_string(self):
        """Test creating from_string."""
        input_obj = ModbusPowerControlInput.from_string("active_power_limit")

        assert input_obj == ModbusPowerControlInput.ACTIVE_POWER_LIMIT

    def test_active_power_limit_str(self):
        """Test string conversion."""
        result = str(ModbusPowerControlInput.ACTIVE_POWER_LIMIT)

        assert result == "active_power_limit"

    def test_get_field_model(self):
        """Test getting field model property."""
        field_model = ModbusPowerControlInput.ACTIVE_POWER_LIMIT.input_model

        assert field_model == ModbusActivePowerLimitInput

    def test_get_field_name(self):
        """Test getting field name property."""
        field_name = ModbusPowerControlInput.ACTIVE_POWER_LIMIT.key

        assert field_name == "active_power_limit"
