"""Tests for wallbox settings module."""

from pydantic import SecretStr

from solaredge2mqtt.services.wallbox.settings import WallboxSettings


class TestWallboxSettings:
    """Tests for WallboxSettings class."""

    def test_wallbox_settings_defaults(self):
        """Test WallboxSettings default values."""
        settings = WallboxSettings()

        assert settings.host is None
        assert settings.password is None
        assert settings.serial is None
        assert settings.retain is False

    def test_wallbox_settings_custom_values(self):
        """Test WallboxSettings with custom values."""
        settings = WallboxSettings(
            host="192.168.1.50",
            password="wallbox_password",
            serial="WB123456",
            retain=True,
        )

        assert settings.host == "192.168.1.50"
        assert settings.password.get_secret_value() == "wallbox_password"
        assert settings.serial == "WB123456"
        assert settings.retain is True

    def test_wallbox_settings_is_configured_true(self):
        """Test is_configured returns True when all required fields set."""
        settings = WallboxSettings(
            host="192.168.1.50",
            password="secret",
            serial="WB123456",
        )

        assert settings.is_configured is True

    def test_wallbox_settings_is_configured_false_no_host(self):
        """Test is_configured returns False without host."""
        settings = WallboxSettings(
            password="secret",
            serial="WB123456",
        )

        assert settings.is_configured is False

    def test_wallbox_settings_is_configured_false_no_password(self):
        """Test is_configured returns False without password."""
        settings = WallboxSettings(
            host="192.168.1.50",
            serial="WB123456",
        )

        assert settings.is_configured is False

    def test_wallbox_settings_is_configured_false_no_serial(self):
        """Test is_configured returns False without serial."""
        settings = WallboxSettings(
            host="192.168.1.50",
            password="secret",
        )

        assert settings.is_configured is False

    def test_wallbox_settings_password_is_secret(self):
        """Test that password is a SecretStr."""
        settings = WallboxSettings(password="my_secret_password")

        assert isinstance(settings.password, SecretStr)
        assert str(settings.password) != "my_secret_password"  # Should be masked
