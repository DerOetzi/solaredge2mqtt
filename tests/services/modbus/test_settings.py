"""Tests for modbus settings module."""


from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.settings import (
    AdvancedControlsSettings,
    ModbusSettings,
    ModbusUnitSettings,
)


class TestAdvancedControlsSettings:
    """Tests for AdvancedControlsSettings enum."""

    def test_advanced_controls_settings_values(self):
        """Test AdvancedControlsSettings enum values."""
        assert AdvancedControlsSettings.ENABLED.value == "enabled"
        assert AdvancedControlsSettings.DISABLED.value == "disabled"
        assert AdvancedControlsSettings.DISABLE.value == "disable"

    def test_advanced_controls_settings_string(self):
        """Test AdvancedControlsSettings string representation."""
        assert str(AdvancedControlsSettings.ENABLED) == "enabled"
        assert str(AdvancedControlsSettings.DISABLED) == "disabled"


class TestModbusUnitSettings:
    """Tests for ModbusUnitSettings class."""

    def test_modbus_unit_settings_defaults(self):
        """Test ModbusUnitSettings default values."""
        settings = ModbusUnitSettings()

        assert settings.unit == 1
        assert len(settings.meter) == 3
        assert len(settings.battery) == 2
        assert settings.role == ModbusUnitRole.LEADER

    def test_modbus_unit_settings_meter_defaults_filled(self):
        """Test that meter array is filled with defaults."""
        settings = ModbusUnitSettings()

        # Default should be True for all meters
        assert all(m is True for m in settings.meter)

    def test_modbus_unit_settings_battery_defaults_filled(self):
        """Test that battery array is filled with defaults."""
        settings = ModbusUnitSettings()

        # Default should be True for all batteries
        assert all(b is True for b in settings.battery)

    def test_modbus_unit_settings_custom_unit(self):
        """Test ModbusUnitSettings with custom unit."""
        settings = ModbusUnitSettings(unit=2)

        assert settings.unit == 2

    def test_modbus_unit_settings_custom_meter_config(self):
        """Test ModbusUnitSettings with custom meter configuration."""
        settings = ModbusUnitSettings(meter=[True, False, True])

        assert settings.meter == [True, False, True]

    def test_modbus_unit_settings_custom_battery_config(self):
        """Test ModbusUnitSettings with custom battery configuration."""
        settings = ModbusUnitSettings(battery=[True, False])

        assert settings.battery == [True, False]

    def test_modbus_unit_settings_partial_meter_config_extended(self):
        """Test that partial meter config is extended to full length."""
        settings = ModbusUnitSettings(meter=[False])

        assert len(settings.meter) == 3
        assert settings.meter[0] is False
        # Remaining should be defaults
        assert settings.meter[1] is True
        assert settings.meter[2] is True


class TestModbusSettings:
    """Tests for ModbusSettings class."""

    def test_modbus_settings_defaults(self):
        """Test ModbusSettings default values."""
        settings = ModbusSettings()

        assert settings.host is None
        assert settings.port == 1502
        assert settings.timeout == 1
        assert settings.check_grid_status is False
        assert settings.advanced_power_controls == AdvancedControlsSettings.DISABLED
        assert settings.follower == []
        assert settings.retain is False

    def test_modbus_settings_custom_values(self):
        """Test ModbusSettings with custom values."""
        settings = ModbusSettings(
            host="192.168.1.100",
            port=502,
            timeout=5,
            check_grid_status=True,
            retain=True,
        )

        assert settings.host == "192.168.1.100"
        assert settings.port == 502
        assert settings.timeout == 5
        assert settings.check_grid_status is True
        assert settings.retain is True

    def test_modbus_settings_advanced_power_controls_enabled(self):
        """Test advanced_power_controls_enabled property."""
        settings_enabled = ModbusSettings(
            advanced_power_controls=AdvancedControlsSettings.ENABLED
        )
        settings_disabled = ModbusSettings(
            advanced_power_controls=AdvancedControlsSettings.DISABLED
        )

        assert settings_enabled.advanced_power_controls_enabled is True
        assert settings_disabled.advanced_power_controls_enabled is False

    def test_modbus_settings_units_without_followers(self):
        """Test units property without followers."""
        settings = ModbusSettings()
        units = settings.units

        assert "leader" in units
        assert len(units) == 1

    def test_modbus_settings_units_with_followers(self):
        """Test units property with followers."""
        settings = ModbusSettings(follower=[{"unit": 2}, {"unit": 3}])
        units = settings.units

        assert "leader" in units
        assert "follower0" in units
        assert "follower1" in units
        assert len(units) == 3

    def test_modbus_settings_has_followers_true(self):
        """Test has_followers returns True with followers."""
        settings = ModbusSettings(follower=[{"unit": 2}])

        assert settings.has_followers is True

    def test_modbus_settings_has_followers_false(self):
        """Test has_followers returns False without followers."""
        settings = ModbusSettings()

        assert settings.has_followers is False

    def test_modbus_settings_follower_role_is_follower(self):
        """Test that followers have FOLLOWER role."""
        settings = ModbusSettings(follower=[{"unit": 2}])

        assert settings.follower[0].role == ModbusUnitRole.FOLLOWER

    def test_modbus_settings_follower_meter_defaults_false(self):
        """Test that follower meter defaults are False."""
        settings = ModbusSettings(follower=[{"unit": 2}])

        assert all(m is False for m in settings.follower[0].meter)

    def test_modbus_settings_follower_battery_defaults_false(self):
        """Test that follower battery defaults are False."""
        settings = ModbusSettings(follower=[{"unit": 2}])

        assert all(b is False for b in settings.follower[0].battery)
