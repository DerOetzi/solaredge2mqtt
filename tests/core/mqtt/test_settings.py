"""Tests for core MQTT settings module."""

import pytest
from pydantic import SecretStr

from solaredge2mqtt.core.mqtt.settings import MQTTSettings


class TestMQTTSettings:
    """Tests for MQTTSettings class."""

    def test_mqtt_settings_defaults(self):
        """Test MQTTSettings default values."""
        settings = MQTTSettings(broker="localhost")

        assert settings.client_id == "solaredge2mqtt"
        assert settings.broker == "localhost"
        assert settings.port == 1883
        assert settings.username is None
        assert settings.password is None
        assert settings.topic_prefix == "solaredge"

    def test_mqtt_settings_custom_values(self):
        """Test MQTTSettings with custom values."""
        settings = MQTTSettings(
            client_id="custom_client",
            broker="mqtt.example.com",
            port=8883,
            username="test_user",
            password="secret123",
            topic_prefix="custom_prefix",
        )

        assert settings.client_id == "custom_client"
        assert settings.broker == "mqtt.example.com"
        assert settings.port == 8883
        assert settings.username == "test_user"
        assert settings.password.get_secret_value() == "secret123"
        assert settings.topic_prefix == "custom_prefix"

    def test_mqtt_settings_kargs_without_credentials(self):
        """Test kargs property without credentials."""
        settings = MQTTSettings(broker="localhost")
        kargs = settings.kargs

        assert kargs == {"identifier": "solaredge2mqtt"}

    def test_mqtt_settings_kargs_with_username_only(self):
        """Test kargs property with username only."""
        settings = MQTTSettings(broker="localhost", username="test_user")
        kargs = settings.kargs

        assert kargs == {
            "identifier": "solaredge2mqtt",
            "username": "test_user",
        }

    def test_mqtt_settings_kargs_with_full_credentials(self):
        """Test kargs property with full credentials."""
        settings = MQTTSettings(
            broker="localhost",
            username="test_user",
            password="secret123",
        )
        kargs = settings.kargs

        assert kargs == {
            "identifier": "solaredge2mqtt",
            "username": "test_user",
            "password": "secret123",
        }

    def test_mqtt_settings_password_is_secret(self):
        """Test that password is a SecretStr."""
        settings = MQTTSettings(broker="localhost", password="secret123")

        assert isinstance(settings.password, SecretStr)
        assert str(settings.password) != "secret123"  # Should be masked

    def test_mqtt_settings_required_broker(self):
        """Test that broker is required."""
        with pytest.raises(Exception):
            MQTTSettings()

    def test_mqtt_settings_custom_client_id(self):
        """Test custom client_id in kargs."""
        settings = MQTTSettings(broker="localhost", client_id="my_client")
        kargs = settings.kargs

        assert kargs["identifier"] == "my_client"
