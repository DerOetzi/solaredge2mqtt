"""Tests for ModbusStorageControl model."""

import pytest

from solaredge2mqtt.services.modbus.models.storage import ModbusStorageControl


class TestModbusStorageControlModel:
    """Tests for the ModbusStorageControl model."""

    @pytest.fixture
    def sample_storage_control_data(self):
        """Sample data for storage control model."""
        return {
            "storage_control_mode": 4,
            "storage_ac_charge_policy": 1,
            "storage_ac_charge_limit": 5000.0,
            "storage_backup_reserve": 20.0,
            "storage_default_mode": 7,
            "storage_command_timeout": 3600,
            "storage_command_mode": 5,
            "storage_charge_limit": 10000.0,
            "storage_discharge_limit": 8000.0,
        }

    def test_storage_control_creation(self, sample_storage_control_data):
        """Test basic storage control model creation."""
        storage = ModbusStorageControl(sample_storage_control_data)

        assert storage.control_mode == 4
        assert storage.control_mode_text == "Remote Control"
        assert storage.ac_charge_policy == 1
        assert storage.ac_charge_policy_text == "Always Allowed"
        assert storage.ac_charge_limit == 5000.0
        assert storage.backup_reserve == 20.0
        assert storage.default_mode == 7
        assert storage.default_mode_text == "Maximize Self Consumption"
        assert storage.command_timeout == 3600
        assert storage.command_mode == 5
        assert storage.command_mode_text == "Discharge to Minimize Import"
        assert storage.charge_limit == 10000.0
        assert storage.discharge_limit == 8000.0

    def test_storage_control_with_defaults(self):
        """Test storage control model with missing data uses defaults."""
        storage = ModbusStorageControl({})

        assert storage.control_mode == 0
        assert storage.control_mode_text == "Disabled"
        assert storage.charge_limit == 0.0
        assert storage.discharge_limit == 0.0

    def test_is_remote_control_enabled_true(self, sample_storage_control_data):
        """Test is_remote_control_enabled when control_mode is 4."""
        storage = ModbusStorageControl(sample_storage_control_data)
        assert storage.is_remote_control_enabled is True

    def test_is_remote_control_enabled_false(self):
        """Test is_remote_control_enabled when control_mode is not 4."""
        data = {"storage_control_mode": 1}
        storage = ModbusStorageControl(data)
        assert storage.is_remote_control_enabled is False

    def test_is_valid_with_valid_data(self, sample_storage_control_data):
        """Test is_valid returns True for valid data."""
        storage = ModbusStorageControl(sample_storage_control_data)
        assert storage.is_valid is True

    def test_is_valid_with_negative_charge_limit(self):
        """Test is_valid returns False for negative charge_limit."""
        data = {"storage_charge_limit": -100}
        storage = ModbusStorageControl(data)
        assert storage.is_valid is False

    def test_is_valid_with_negative_discharge_limit(self):
        """Test is_valid returns False for negative discharge_limit."""
        data = {"storage_charge_limit": 100, "storage_discharge_limit": -100}
        storage = ModbusStorageControl(data)
        assert storage.is_valid is False

    def test_is_valid_with_backup_reserve_out_of_range(self):
        """Test is_valid returns False for backup_reserve out of range."""
        data = {
            "storage_charge_limit": 100,
            "storage_discharge_limit": 100,
            "storage_backup_reserve": 150
        }
        storage = ModbusStorageControl(data)
        assert storage.is_valid is False

    def test_control_mode_text_mapping(self):
        """Test all control mode text mappings."""
        mode_texts = {
            0: "Disabled",
            1: "Maximize Self Consumption",
            2: "Time of Use",
            3: "Backup Only",
            4: "Remote Control",
        }

        for mode, expected_text in mode_texts.items():
            data = {"storage_control_mode": mode}
            storage = ModbusStorageControl(data)
            assert storage.control_mode_text == expected_text

    def test_command_mode_text_mapping(self):
        """Test command mode text mappings."""
        mode_texts = {
            0: "Off",
            1: "Charge from Clipped Solar Power",
            2: "Charge from Solar Power",
            3: "Charge from Solar Power and Grid",
            4: "Discharge to Maximize Export",
            5: "Discharge to Minimize Import",
            7: "Maximize Self Consumption",
        }

        for mode, expected_text in mode_texts.items():
            data = {"storage_command_mode": mode}
            storage = ModbusStorageControl(data)
            assert storage.command_mode_text == expected_text

    def test_ac_charge_policy_text_mapping(self):
        """Test AC charge policy text mappings."""
        policy_texts = {
            0: "Disabled",
            1: "Always Allowed",
            2: "Fixed Energy Limit",
            3: "Percent of Production",
        }

        for policy, expected_text in policy_texts.items():
            data = {"storage_ac_charge_policy": policy}
            storage = ModbusStorageControl(data)
            assert storage.ac_charge_policy_text == expected_text
