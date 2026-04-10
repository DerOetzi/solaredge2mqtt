"""Tests for monitoring settings module."""

import pytest
from pydantic import SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException
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
        settings = MonitoringSettings.model_validate(
            {
                "site_id": "12345",
                "username": "test_user",
                "password": "test_password",
                "retain": True,
            }
        )

        assert settings.site_id_secret == "12345"
        assert settings.username == "test_user"
        assert settings.password_secret == "test_password"
        assert settings.retain is True

    def test_monitoring_settings_is_configured_true(self):
        """Test is_configured returns True when all required fields are set."""
        settings = MonitoringSettings.model_validate(
            {
                "site_id": "12345",
                "username": "test_user",
                "password": "test_password",
            }
        )

        assert settings.is_configured is True

    def test_monitoring_settings_is_configured_false_no_site_id(self):
        """Test is_configured returns False when site_id is missing."""
        settings = MonitoringSettings.model_validate(
            {
                "username": "test_user",
                "password": "test_password",
            }
        )

        assert settings.is_configured is False

    def test_monitoring_settings_is_configured_false_no_username(self):
        """Test is_configured returns False when username is missing."""
        settings = MonitoringSettings.model_validate(
            {
                "site_id": "12345",
                "password": "test_password",
            }
        )

        assert settings.is_configured is False

    def test_monitoring_settings_is_configured_false_no_password(self):
        """Test is_configured returns False when password is missing."""
        settings = MonitoringSettings.model_validate(
            {
                "site_id": "12345",
                "username": "test_user",
            }
        )

        assert settings.is_configured is False

    def test_monitoring_settings_is_configured_false_empty(self):
        """Test is_configured returns False when no fields are set."""
        settings = MonitoringSettings()

        assert settings.is_configured is False

    def test_monitoring_settings_password_is_secret(self):
        """Test that password is a SecretStr."""
        settings = MonitoringSettings.model_validate({"password": "my_secret_password"})

        assert isinstance(settings.password, SecretStr)
        # Should be masked
        assert str(settings.password) != "my_secret_password"

    def test_monitoring_settings_retain_default_is_false(self):
        """Test retain field defaults to False."""
        settings = MonitoringSettings.model_validate(
            {
                "site_id": "12345",
                "username": "test_user",
                "password": "test_password",
            }
        )

        assert settings.retain is False

    def test_site_id_secret_raises_when_missing(self):
        """site_id_secret should raise for missing site_id."""
        settings = MonitoringSettings()

        with pytest.raises(ConfigurationException):
            _ = settings.site_id_secret

    def test_username_value_raises_when_missing(self):
        """username_value should raise for missing username."""
        settings = MonitoringSettings()

        with pytest.raises(ConfigurationException):
            _ = settings.username_value

    def test_password_secret_raises_when_missing(self):
        """password_secret should raise for missing password."""
        settings = MonitoringSettings()

        with pytest.raises(ConfigurationException):
            _ = settings.password_secret

    def test_username_value_returns_username(self):
        """username_value should return configured username."""
        settings = MonitoringSettings(username="monitor-user")

        assert settings.username_value == "monitor-user"
