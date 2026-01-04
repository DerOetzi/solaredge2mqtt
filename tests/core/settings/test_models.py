"""Tests for core settings models module."""

import tempfile
from pathlib import Path

from solaredge2mqtt.core.logging.models import LoggingLevelEnum
from solaredge2mqtt.core.settings.loader import ConfigurationLoader
from solaredge2mqtt.core.settings.models import LocationSettings


class TestLocationSettings:
    """Tests for LocationSettings class."""

    def test_location_settings_creation(self):
        """Test LocationSettings creation with valid data."""
        location = LocationSettings(latitude=52.520008, longitude=13.404954)

        assert location.latitude == 52.520008
        assert location.longitude == 13.404954

    def test_location_settings_validation(self):
        """Test LocationSettings validation."""
        try:
            LocationSettings(latitude="invalid", longitude=13.404954)
            raise AssertionError("Expected validation error for invalid latitude")
        except (ValueError, TypeError):
            pass


class TestServiceSettings:
    """Tests for ServiceSettings class."""

    def test_service_settings_loads_from_yaml(self):
        """Test ServiceSettings loads configuration from YAML files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create configuration file
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "interval: 10\n"
                "logging_level: DEBUG\n"
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "  port: 1502\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "  port: 1883\n"
            )

            settings = ConfigurationLoader.load_configuration(tmpdir)

            assert settings.interval == 10
            assert settings.logging_level == LoggingLevelEnum.DEBUG
            assert settings.modbus.host == "192.168.1.100"
            assert settings.modbus.port == 1502
            assert settings.mqtt.broker == "mqtt.example.com"
            assert settings.mqtt.port == 1883

    def test_service_settings_with_override_data(self):
        """Test ServiceSettings with override data for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal configuration file
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
            )

            # Override interval for testing
            settings = ConfigurationLoader.load_configuration(
                tmpdir, override_data={"interval": 15}
            )

            assert settings.interval == 15
            assert settings.modbus.host == "192.168.1.100"
            assert settings.mqtt.broker == "mqtt.example.com"

    def test_is_location_configured_true(self):
        """Test is_location_configured returns True when location is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "location:\n"
                "  latitude: 52.520008\n"
                "  longitude: 13.404954\n"
            )

            settings = ConfigurationLoader.load_configuration(tmpdir)

            assert settings.is_location_configured is True
            assert settings.location.latitude == 52.520008
            assert settings.location.longitude == 13.404954

    def test_is_location_configured_false(self):
        """Test is_location_configured returns False when location is not set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
            )

            settings = ConfigurationLoader.load_configuration(tmpdir)

            assert settings.is_location_configured is False
            assert settings.location is None

    def test_is_influxdb_configured_true(self):
        """Test is_influxdb_configured returns True when influxdb is set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "influxdb:\n"
                "  host: http://localhost\n"
                "  port: 8086\n"
                "  token: !secret influxdb_token\n"
                "  org: test_org\n"
            )
            secrets_file.write_text("influxdb_token: test_token\n")

            settings = ConfigurationLoader.load_configuration(tmpdir)

            assert settings.is_influxdb_configured is True
            assert settings.influxdb.host == "http://localhost"

    def test_is_influxdb_configured_false(self):
        """Test is_influxdb_configured returns False when influxdb is not set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
            )

            settings = ConfigurationLoader.load_configuration(tmpdir)

            assert settings.is_influxdb_configured is False
            assert settings.influxdb is None

    def test_is_weather_configured_requires_location(self):
        """Test is_weather_configured returns False when location is not set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "weather:\n"
                "  api_key: !secret weather_api_key\n"
            )
            secrets_file.write_text("weather_api_key: test_key\n")

            settings = ConfigurationLoader.load_configuration(tmpdir)

            # Weather configured but location not, returns False
            assert settings.is_weather_configured is False
            assert settings.is_location_configured is False

    def test_is_forecast_configured_requires_location_and_weather(self):
        """Test is_forecast_configured requires both location and weather."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "forecast:\n"
                "  enable: true\n"
            )

            settings = ConfigurationLoader.load_configuration(tmpdir)

            # Forecast enabled but missing location and weather
            assert settings.is_forecast_configured is False

    def test_default_values(self):
        """Test ServiceSettings has correct default values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
            )

            settings = ConfigurationLoader.load_configuration(tmpdir)

            assert settings.interval == 5
            assert settings.logging_level == LoggingLevelEnum.INFO
            assert settings.powerflow is not None
            assert settings.energy is not None
            assert settings.prices is not None
