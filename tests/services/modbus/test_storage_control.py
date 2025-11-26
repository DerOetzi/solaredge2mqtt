"""Tests for storage control model and input validation."""

import pytest

from solaredge2mqtt.services.modbus.models.storage_control import StorageControl
from solaredge2mqtt.services.modbus.models.inputs import (
    StorageControlModeInput,
    StorageDefaultModeInput,
    StorageChargeLimitInput,
    StorageDischargeLimitInput,
    StorageBackupReserveInput,
    StorageCommandTimeoutInput,
    ModbusStorageControlInput,
)


class TestStorageControl:
    """Tests for StorageControl model."""

    def test_storage_control_from_data(self):
        """Test creating StorageControl from raw data."""
        raw_data = {
            "control_mode": 1,
            "ac_charge_policy": 0,
            "ac_charge_limit": 1000.0,
            "backup_reserve": 20.0,
            "default_mode": 7,
            "command_timeout": 3600,
            "command_mode": 0,
            "charge_limit": 5000.0,
            "discharge_limit": 5000.0,
        }

        storage = StorageControl(raw_data)

        assert storage.control_mode == 1
        assert storage.control_mode_text == "Maximize Self Consumption"
        assert storage.ac_charge_policy == 0
        assert storage.ac_charge_policy_text == "Disabled"
        assert storage.ac_charge_limit == 1000.0
        assert storage.backup_reserve == 20.0
        assert storage.default_mode == 7
        assert storage.default_mode_text == "Maximize Self Consumption"
        assert storage.command_timeout == 3600
        assert storage.command_mode == 0
        assert storage.charge_limit == 5000.0
        assert storage.discharge_limit == 5000.0

    def test_storage_control_remote_mode(self):
        """Test is_remote_control_mode property."""
        remote_storage = StorageControl({"control_mode": 4})
        non_remote_storage = StorageControl({"control_mode": 1})

        assert remote_storage.is_remote_control_mode is True
        assert non_remote_storage.is_remote_control_mode is False

    def test_storage_control_is_valid(self):
        """Test is_valid property."""
        valid_storage = StorageControl({"control_mode": 1})
        invalid_storage = StorageControl({})

        assert valid_storage.is_valid is True
        assert invalid_storage.is_valid is False

    def test_storage_control_none_values(self):
        """Test StorageControl handles None values."""
        storage = StorageControl(None)

        assert storage.control_mode is None
        assert storage.charge_limit is None
        assert storage.discharge_limit is None

    def test_storage_control_topic_prefix(self):
        """Test generate_topic_prefix class method."""
        assert StorageControl.generate_topic_prefix() == "modbus/storage_control"
        assert (
            StorageControl.generate_topic_prefix("leader")
            == "modbus/leader/storage_control"
        )

    def test_storage_control_unknown_mode_text(self):
        """Test unknown control mode produces Unknown text."""
        storage = StorageControl({"control_mode": 99})

        assert storage.control_mode == 99
        assert storage.control_mode_text == "Unknown"


class TestStorageControlInputs:
    """Tests for storage control input models."""

    def test_control_mode_input_valid(self):
        """Test valid control mode input."""
        input_data = StorageControlModeInput(mode=1)
        assert input_data.mode == 1

    def test_control_mode_input_boundary(self):
        """Test control mode input boundaries."""
        min_input = StorageControlModeInput(mode=0)
        max_input = StorageControlModeInput(mode=4)

        assert min_input.mode == 0
        assert max_input.mode == 4

    def test_control_mode_input_invalid(self):
        """Test invalid control mode input."""
        with pytest.raises(ValueError):
            StorageControlModeInput(mode=5)

        with pytest.raises(ValueError):
            StorageControlModeInput(mode=-1)

    def test_default_mode_input_valid(self):
        """Test valid default mode inputs."""
        for valid_mode in [0, 1, 2, 3, 4, 5, 7]:
            input_data = StorageDefaultModeInput(mode=valid_mode)
            assert input_data.mode == valid_mode

    def test_default_mode_input_invalid(self):
        """Test invalid default mode (mode 6 is not valid)."""
        with pytest.raises(ValueError):
            StorageDefaultModeInput(mode=6)

    def test_charge_limit_input_valid(self):
        """Test valid charge limit input."""
        input_data = StorageChargeLimitInput(limit=5000.0)
        assert input_data.limit == 5000.0

    def test_charge_limit_input_boundaries(self):
        """Test charge limit boundaries."""
        min_input = StorageChargeLimitInput(limit=0)
        max_input = StorageChargeLimitInput(limit=1000000)

        assert min_input.limit == 0
        assert max_input.limit == 1000000

    def test_charge_limit_input_invalid(self):
        """Test invalid charge limit."""
        with pytest.raises(ValueError):
            StorageChargeLimitInput(limit=-1)

        with pytest.raises(ValueError):
            StorageChargeLimitInput(limit=1000001)

    def test_discharge_limit_input_valid(self):
        """Test valid discharge limit input."""
        input_data = StorageDischargeLimitInput(limit=5000.0)
        assert input_data.limit == 5000.0

    def test_backup_reserve_input_valid(self):
        """Test valid backup reserve input."""
        input_data = StorageBackupReserveInput(percent=20.0)
        assert input_data.percent == 20.0

    def test_backup_reserve_input_boundaries(self):
        """Test backup reserve boundaries."""
        min_input = StorageBackupReserveInput(percent=0)
        max_input = StorageBackupReserveInput(percent=100)

        assert min_input.percent == 0
        assert max_input.percent == 100

    def test_backup_reserve_input_invalid(self):
        """Test invalid backup reserve."""
        with pytest.raises(ValueError):
            StorageBackupReserveInput(percent=-1)

        with pytest.raises(ValueError):
            StorageBackupReserveInput(percent=101)

    def test_command_timeout_input_valid(self):
        """Test valid command timeout input."""
        input_data = StorageCommandTimeoutInput(seconds=3600)
        assert input_data.seconds == 3600

    def test_command_timeout_input_boundaries(self):
        """Test command timeout boundaries."""
        min_input = StorageCommandTimeoutInput(seconds=0)
        max_input = StorageCommandTimeoutInput(seconds=86400)

        assert min_input.seconds == 0
        assert max_input.seconds == 86400

    def test_command_timeout_input_invalid(self):
        """Test invalid command timeout."""
        with pytest.raises(ValueError):
            StorageCommandTimeoutInput(seconds=-1)

        with pytest.raises(ValueError):
            StorageCommandTimeoutInput(seconds=86401)


class TestModbusStorageControlInput:
    """Tests for ModbusStorageControlInput enum."""

    def test_control_mode_enum(self):
        """Test CONTROL_MODE enum value."""
        input_type = ModbusStorageControlInput.CONTROL_MODE
        assert input_type.key == "control_mode"
        assert input_type.input_model == StorageControlModeInput

    def test_charge_limit_enum(self):
        """Test CHARGE_LIMIT enum value."""
        input_type = ModbusStorageControlInput.CHARGE_LIMIT
        assert input_type.key == "charge_limit"
        assert input_type.input_model == StorageChargeLimitInput

    def test_discharge_limit_enum(self):
        """Test DISCHARGE_LIMIT enum value."""
        input_type = ModbusStorageControlInput.DISCHARGE_LIMIT
        assert input_type.key == "discharge_limit"
        assert input_type.input_model == StorageDischargeLimitInput

    def test_from_string(self):
        """Test from_string class method."""
        input_type = ModbusStorageControlInput.from_string("control_mode")
        assert input_type == ModbusStorageControlInput.CONTROL_MODE

        input_type = ModbusStorageControlInput.from_string("charge_limit")
        assert input_type == ModbusStorageControlInput.CHARGE_LIMIT
