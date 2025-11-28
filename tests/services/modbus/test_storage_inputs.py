"""Tests for storage control input models."""

import pytest
from pydantic import ValidationError

from solaredge2mqtt.services.modbus.models.inputs import (
    ModbusStorageChargeLimitInput,
    ModbusStorageCommandModeInput,
    ModbusStorageCommandTimeoutInput,
    ModbusStorageControlInput,
    ModbusStorageDischargeLimitInput,
)


class TestModbusStorageChargeLimitInput:
    """Tests for ModbusStorageChargeLimitInput."""

    def test_valid_charge_limit(self):
        """Test valid charge limit values."""
        input_model = ModbusStorageChargeLimitInput(limit=5000.0)
        assert input_model.limit == 5000.0

    def test_zero_charge_limit(self):
        """Test zero charge limit is valid."""
        input_model = ModbusStorageChargeLimitInput(limit=0)
        assert input_model.limit == 0

    def test_max_charge_limit(self):
        """Test maximum charge limit is valid."""
        input_model = ModbusStorageChargeLimitInput(limit=1000000)
        assert input_model.limit == 1000000

    def test_negative_charge_limit_invalid(self):
        """Test negative charge limit raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageChargeLimitInput(limit=-100)

    def test_exceeds_max_charge_limit_invalid(self):
        """Test exceeding max charge limit raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageChargeLimitInput(limit=1000001)


class TestModbusStorageDischargeLimitInput:
    """Tests for ModbusStorageDischargeLimitInput."""

    def test_valid_discharge_limit(self):
        """Test valid discharge limit values."""
        input_model = ModbusStorageDischargeLimitInput(limit=8000.0)
        assert input_model.limit == 8000.0

    def test_zero_discharge_limit(self):
        """Test zero discharge limit is valid."""
        input_model = ModbusStorageDischargeLimitInput(limit=0)
        assert input_model.limit == 0

    def test_negative_discharge_limit_invalid(self):
        """Test negative discharge limit raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageDischargeLimitInput(limit=-100)


class TestModbusStorageCommandModeInput:
    """Tests for ModbusStorageCommandModeInput."""

    def test_valid_command_modes(self):
        """Test all valid command mode values."""
        for mode in [0, 1, 2, 3, 4, 5, 7]:
            input_model = ModbusStorageCommandModeInput(mode=mode)
            assert input_model.mode == mode

    def test_negative_mode_invalid(self):
        """Test negative mode raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageCommandModeInput(mode=-1)

    def test_exceeds_max_mode_invalid(self):
        """Test mode exceeding 7 raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageCommandModeInput(mode=8)


class TestModbusStorageCommandTimeoutInput:
    """Tests for ModbusStorageCommandTimeoutInput."""

    def test_valid_timeout(self):
        """Test valid timeout values."""
        input_model = ModbusStorageCommandTimeoutInput(timeout=3600)
        assert input_model.timeout == 3600

    def test_zero_timeout(self):
        """Test zero timeout is valid."""
        input_model = ModbusStorageCommandTimeoutInput(timeout=0)
        assert input_model.timeout == 0

    def test_max_timeout(self):
        """Test max timeout (24h) is valid."""
        input_model = ModbusStorageCommandTimeoutInput(timeout=86400)
        assert input_model.timeout == 86400

    def test_negative_timeout_invalid(self):
        """Test negative timeout raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageCommandTimeoutInput(timeout=-1)

    def test_exceeds_max_timeout_invalid(self):
        """Test exceeding max timeout raises validation error."""
        with pytest.raises(ValidationError):
            ModbusStorageCommandTimeoutInput(timeout=86401)


class TestModbusStorageControlInput:
    """Tests for ModbusStorageControlInput enum."""

    def test_enum_members(self):
        """Test all enum members exist."""
        assert hasattr(ModbusStorageControlInput, 'CHARGE_LIMIT')
        assert hasattr(ModbusStorageControlInput, 'DISCHARGE_LIMIT')
        assert hasattr(ModbusStorageControlInput, 'COMMAND_MODE')
        assert hasattr(ModbusStorageControlInput, 'COMMAND_TIMEOUT')

    def test_charge_limit_input_model(self):
        """Test CHARGE_LIMIT enum has correct input model."""
        assert (ModbusStorageControlInput.CHARGE_LIMIT.input_model
                == ModbusStorageChargeLimitInput)

    def test_discharge_limit_input_model(self):
        """Test DISCHARGE_LIMIT enum has correct input model."""
        assert (ModbusStorageControlInput.DISCHARGE_LIMIT.input_model
                == ModbusStorageDischargeLimitInput)

    def test_command_mode_input_model(self):
        """Test COMMAND_MODE enum has correct input model."""
        assert (ModbusStorageControlInput.COMMAND_MODE.input_model
                == ModbusStorageCommandModeInput)

    def test_command_timeout_input_model(self):
        """Test COMMAND_TIMEOUT enum has correct input model."""
        assert (ModbusStorageControlInput.COMMAND_TIMEOUT.input_model
                == ModbusStorageCommandTimeoutInput)

    def test_enum_keys(self):
        """Test enum keys are correctly set."""
        assert ModbusStorageControlInput.CHARGE_LIMIT.key == "charge_limit"
        assert ModbusStorageControlInput.DISCHARGE_LIMIT.key == "discharge_limit"
        assert ModbusStorageControlInput.COMMAND_MODE.key == "command_mode"
        assert ModbusStorageControlInput.COMMAND_TIMEOUT.key == "command_timeout"
