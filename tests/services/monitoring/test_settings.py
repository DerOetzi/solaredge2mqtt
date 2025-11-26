"""Tests for monitoring settings module."""

from pydantic import SecretStr

from solaredge2mqtt.services.monitoring.settings import MonitoringSettings


class TestMonitoringSettings:
    """Tests for MonitoringSettings class."""

    def test_monitoring_settings_defaults(self):
        """Test MonitoringSettings default values."""
        settings = MonitoringSettings()

        assert settings.site_id is None
        assert settings.username is None
        assert settings.password is None
        assert settings.retain is False

    def test_monitoring_settings_custom_values(self):
        """Test MonitoringSettings with custom values."""
        settings = MonitoringSettings(
            site_id="12345",
            username="test_user",
            password="test_password",
            retain=True,
        )

        assert settings.site_id == "12345"
        assert settings.username == "test_user"
        assert settings.password.get_secret_value() == "test_password"
        assert settings.retain is True

    def test_monitoring_settings_is_configured_true(self):
        """Test is_configured returns True when all required fields are set."""
        settings = MonitoringSettings(
            site_id="12345",
            username="test_user",
            password="test_password",
        )

        assert settings.is_configured is True

    def test_monitoring_settings_is_configured_false_no_site_id(self):
        """Test is_configured returns False when site_id is missing."""
        settings = MonitoringSettings(
            username="test_user",
            password="test_password",
        )

        assert settings.is_configured is False

    def test_monitoring_settings_is_configured_false_no_username(self):
        """Test is_configured returns False when username is missing."""
        settings = MonitoringSettings(
            site_id="12345",
            password="test_password",
        )

        assert settings.is_configured is False

    def test_monitoring_settings_is_configured_false_no_password(self):
        """Test is_configured returns False when password is missing."""
        settings = MonitoringSettings(
            site_id="12345",
            username="test_user",
        )

        assert settings.is_configured is False

    def test_monitoring_settings_is_configured_false_empty(self):
        """Test is_configured returns False when no fields are set."""
        settings = MonitoringSettings()

        assert settings.is_configured is False

    def test_monitoring_settings_password_is_secret(self):
        """Test that password is a SecretStr."""
        settings = MonitoringSettings(password="my_secret_password")

        assert isinstance(settings.password, SecretStr)
        assert str(settings.password) != "my_secret_password"  # Should be masked

    def test_monitoring_settings_retain_default_is_false(self):
        """Test retain field defaults to False."""
        settings = MonitoringSettings(
            site_id="12345",
            username="test_user",
            password="test_password",
        )

        assert settings.retain is False
