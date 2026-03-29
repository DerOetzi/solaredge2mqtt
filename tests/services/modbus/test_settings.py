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

        # Default should be True for meter0, False for meter1 and meter2
        assert settings.meter[0] is True
        assert settings.meter[1] is False
        assert settings.meter[2] is False

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
        # Remaining should be pattern defaults (False for meter1 and meter2)
        assert settings.meter[1] is False
        assert settings.meter[2] is False

    def test_modbus_unit_settings_invalid_meter_item_uses_defaults(self):
        """Non-bool/string meter values should fall back to pattern defaults."""
        values = {"meter": [123, True, "false"]}

        filled = ModbusUnitSettings._fill_defaults_array_with_pattern(
            "meter",
            values,
            [True, False, False],
        )

        assert filled["meter"] == [True, True, False]

    def test_modbus_unit_settings_invalid_battery_item_and_extend(self):
        """Non-bool/string battery values should default and extend list."""
        values = {"battery": [None]}

        filled = ModbusUnitSettings._fill_defaults_array(
            "battery",
            values,
            2,
            "true",
        )

        assert filled["battery"] == [True, "true"]


class TestModbusSettings:
    """Tests for ModbusSettings class."""

    def test_modbus_settings_defaults(self):
        """Test ModbusSettings default values."""
        settings = ModbusSettings(host="test")

        assert settings.host == "test"
        assert settings.port == 1502
        assert settings.timeout == 1
        assert settings.check_grid_status is False
        assert settings.advanced_power_controls == AdvancedControlsSettings.DISABLED
        assert settings.follower == []
        assert settings.retain is False

    def test_modbus_settings_custom_values(self):
        """Test ModbusSettings with custom values."""
        settings = ModbusSettings(
            host="192.168.1.100",  # noqa: S1313
            port=502,
            timeout=5,
            check_grid_status=True,
            retain=True,
        )

        assert settings.host == "192.168.1.100"  # noqa: S1313
        assert settings.port == 502
        assert settings.timeout == 5
        assert settings.check_grid_status is True
        assert settings.retain is True

    def test_modbus_settings_advanced_power_controls_enabled(self):
        """Test advanced_power_controls_enabled property."""
        settings_enabled = ModbusSettings(
            host="test", advanced_power_controls=AdvancedControlsSettings.ENABLED
        )
        settings_disabled = ModbusSettings(
            host="test", advanced_power_controls=AdvancedControlsSettings.DISABLED
        )

        assert settings_enabled.advanced_power_controls_enabled is True
        assert settings_disabled.advanced_power_controls_enabled is False

    def test_modbus_settings_units_without_followers(self):
        """Test units property without followers."""
        settings = ModbusSettings(host="test")
        units = settings.units

        assert "leader" in units
        assert len(units) == 1

    def test_modbus_settings_units_with_followers(self):
        """Test units property with followers."""
        settings = ModbusSettings(
            host="test",
            follower=[{"unit": 2}, {"unit": 3}],  # pyright: ignore[reportArgumentType]
        )
        units = settings.units

        assert "leader" in units
        assert "follower0" in units
        assert "follower1" in units
        assert len(units) == 3

    def test_modbus_settings_has_followers_true(self):
        """Test has_followers returns True with followers."""
        settings = ModbusSettings(host="test", follower=[{"unit": 2}])  # pyright: ignore[reportArgumentType]

        assert settings.has_followers is True

    def test_modbus_settings_has_followers_false(self):
        """Test has_followers returns False without followers."""
        settings = ModbusSettings(host="test")

        assert settings.has_followers is False

    def test_modbus_settings_follower_role_is_follower(self):
        """Test that followers have FOLLOWER role."""
        settings = ModbusSettings(host="test", follower=[{"unit": 2}])  # pyright: ignore[reportArgumentType]

        assert settings.follower[0].role == ModbusUnitRole.FOLLOWER

    def test_modbus_settings_follower_meter_defaults_false(self):
        """Test that follower meter defaults are False."""
        settings = ModbusSettings(host="test", follower=[{"unit": 2}])  # pyright: ignore[reportArgumentType]

        assert all(m is False for m in settings.follower[0].meter)

    def test_modbus_settings_follower_battery_defaults_false(self):
        """Test that follower battery defaults are False."""
        settings = ModbusSettings(host="test", follower=[{"unit": 2}])  # pyright: ignore[reportArgumentType]

        assert all(b is False for b in settings.follower[0].battery)

    def test_modbus_settings_follower_non_bool_values_normalized(self):
        """Follower non-boolean values should normalize to false defaults."""
        settings = ModbusSettings(
            host="test",
            follower=[
                {
                    "unit": 2,
                    "meter": [None],
                    "battery": [object()],
                }
            ],  # pyright: ignore[reportArgumentType]
        )

        assert settings.follower[0].meter == [False, False, False]
        assert settings.follower[0].battery == [False, False]
