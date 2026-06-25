"""Tests for modbus settings module."""

from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.settings import (
    AdvancedControlsSettings,
    ModbusFollowerSettings,
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

    def test_modbus_settings_follower_with_own_host(self):
        """Test that a follower can have its own host and port."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[
                {"unit": 2, "host": "192.168.1.11", "port": 502},  # pyright: ignore[reportArgumentType]
            ],
        )

        assert isinstance(settings.follower[0], ModbusFollowerSettings)
        assert settings.follower[0].host == "192.168.1.11"  # noqa: S1313
        assert settings.follower[0].port == 502

    def test_modbus_settings_follower_with_own_host_no_port(self):
        """Test that a follower can have only its own host without a custom port."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[
                {"unit": 2, "host": "192.168.1.11"},  # pyright: ignore[reportArgumentType]
            ],
        )

        assert settings.follower[0].host == "192.168.1.11"  # noqa: S1313
        assert settings.follower[0].port is None

    def test_modbus_settings_follower_without_own_host_defaults_to_none(self):
        """Test that follower host defaults to None when not specified."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[{"unit": 2}],  # pyright: ignore[reportArgumentType]
        )

        assert settings.follower[0].host is None
        assert settings.follower[0].port is None

    def test_unit_host_returns_leader_host_for_leader(self):
        """unit_host returns the leader's host for unit_key 'leader'."""
        settings = ModbusSettings(host="192.168.1.10")  # noqa: S1313

        assert settings.unit_host("leader") == "192.168.1.10"  # noqa: S1313

    def test_unit_host_falls_back_to_leader_for_follower_without_host(self):
        """unit_host falls back to leader's host when follower has no own host."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[{"unit": 2}],  # pyright: ignore[reportArgumentType]
        )

        assert settings.unit_host("follower0") == "192.168.1.10"  # noqa: S1313

    def test_unit_host_returns_follower_host_when_set(self):
        """unit_host returns the follower's own host when configured."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[{"unit": 2, "host": "192.168.1.11"}],  # pyright: ignore[reportArgumentType]
        )

        assert settings.unit_host("follower0") == "192.168.1.11"  # noqa: S1313

    def test_unit_port_returns_leader_port_for_leader(self):
        """unit_port returns the leader's port for unit_key 'leader'."""
        settings = ModbusSettings(host="192.168.1.10", port=502)  # noqa: S1313

        assert settings.unit_port("leader") == 502

    def test_unit_port_falls_back_to_leader_for_follower_without_port(self):
        """unit_port falls back to leader's port when follower has no own port."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[{"unit": 2, "host": "192.168.1.11"}],  # pyright: ignore[reportArgumentType]
        )

        assert settings.unit_port("follower0") == 1502

    def test_unit_port_returns_follower_port_when_set(self):
        """unit_port returns the follower's own port when configured."""
        settings = ModbusSettings(
            host="192.168.1.10",  # noqa: S1313
            follower=[{"unit": 2, "host": "192.168.1.11", "port": 502}],  # pyright: ignore[reportArgumentType]
        )

        assert settings.unit_port("follower0") == 502
