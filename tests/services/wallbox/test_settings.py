"""Tests for wallbox settings module."""

import pytest
from pydantic import SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException
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
            host="192.168.1.50",  # noqa: S1313
            password=SecretStr("wallbox_password"),
            serial=SecretStr("WB123456"),
            retain=True,
        )

        assert settings.host == "192.168.1.50"  # noqa: S1313
        assert settings.password_secret == "wallbox_password"
        assert settings.serial_secret == "WB123456"
        assert settings.retain is True

    def test_wallbox_settings_is_configured_true(self):
        """Test is_configured returns True when all required fields set."""
        settings = WallboxSettings(
            host="192.168.1.50",  # noqa: S1313
            password=SecretStr("secret"),
            serial=SecretStr("WB123456"),
        )

        assert settings.is_configured is True

    def test_wallbox_settings_is_configured_false_no_host(self):
        """Test is_configured returns False without host."""
        settings = WallboxSettings(
            password=SecretStr("secret"),
            serial=SecretStr("WB123456"),
        )

        assert settings.is_configured is False

    def test_wallbox_settings_is_configured_false_no_password(self):
        """Test is_configured returns False without password."""
        settings = WallboxSettings(
            host="192.168.1.50",  # noqa: S1313
            serial=SecretStr("WB123456"),
        )

        assert settings.is_configured is False

    def test_wallbox_settings_is_configured_false_no_serial(self):
        """Test is_configured returns False without serial."""
        settings = WallboxSettings(
            host="192.168.1.50",  # noqa: S1313
            password=SecretStr("secret"),
        )

        assert settings.is_configured is False

    def test_wallbox_settings_password_is_secret(self):
        """Test that password is a SecretStr."""
        settings = WallboxSettings(password=SecretStr("my_secret_password"))

        assert isinstance(settings.password, SecretStr)
        # Should be masked
        assert str(settings.password) != "my_secret_password"

    def test_password_secret_raises_when_missing(self):
        """password_secret should raise when password is missing."""
        settings = WallboxSettings(host="192.168.1.50")  # noqa: S1313

        with pytest.raises(ConfigurationException):
            _ = settings.password_secret

    def test_serial_secret_raises_when_missing(self):
        """serial_secret should raise when serial is missing."""
        settings = WallboxSettings(host="192.168.1.50")  # noqa: S1313

        with pytest.raises(ConfigurationException):
            _ = settings.serial_secret
