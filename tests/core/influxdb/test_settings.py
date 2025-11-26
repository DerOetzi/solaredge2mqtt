"""Tests for core InfluxDB settings module."""

from pydantic import SecretStr

from solaredge2mqtt.core.influxdb.settings import (
    SECONDS_PER_2_YEARS,
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    SECONDS_PER_YEAR,
    InfluxDBSettings,
)


class TestInfluxDBConstants:
    """Tests for InfluxDB constants."""

    def test_seconds_per_hour(self):
        """Test SECONDS_PER_HOUR constant."""
        assert SECONDS_PER_HOUR == 3600

    def test_seconds_per_day(self):
        """Test SECONDS_PER_DAY constant."""
        assert SECONDS_PER_DAY == 86400

    def test_seconds_per_year(self):
        """Test SECONDS_PER_YEAR constant."""
        assert SECONDS_PER_YEAR == 86400 * 365

    def test_seconds_per_2_years(self):
        """Test SECONDS_PER_2_YEARS constant."""
        assert SECONDS_PER_2_YEARS == 86400 * 365 * 2


class TestInfluxDBSettings:
    """Tests for InfluxDBSettings class."""

    def test_influxdb_settings_defaults(self):
        """Test InfluxDBSettings default values."""
        settings = InfluxDBSettings()

        assert settings.host is None
        assert settings.port == 8086
        assert settings.token is None
        assert settings.org is None
        assert settings.bucket == "solaredge"
        assert settings.retention == SECONDS_PER_2_YEARS
        assert settings.retention_raw == 25

    def test_influxdb_settings_custom_values(self):
        """Test InfluxDBSettings with custom values."""
        settings = InfluxDBSettings(
            host="influxdb.example.com",
            port=8087,
            token="my_token",
            org="my_org",
            bucket="custom_bucket",
            retention=SECONDS_PER_YEAR,
            retention_raw=12,
        )

        assert settings.host == "influxdb.example.com"
        assert settings.port == 8087
        assert settings.token.get_secret_value() == "my_token"
        assert settings.org == "my_org"
        assert settings.bucket == "custom_bucket"
        assert settings.retention == SECONDS_PER_YEAR
        assert settings.retention_raw == 12

    def test_influxdb_settings_url_without_protocol(self):
        """Test url property adds https:// when no protocol."""
        settings = InfluxDBSettings(host="localhost", port=8086)

        assert settings.url == "https://localhost:8086"

    def test_influxdb_settings_url_with_http(self):
        """Test url property preserves http://."""
        settings = InfluxDBSettings(host="http://localhost", port=8086)

        assert settings.url == "http://localhost:8086"

    def test_influxdb_settings_url_with_https(self):
        """Test url property preserves https://."""
        settings = InfluxDBSettings(host="https://localhost", port=8086)

        assert settings.url == "https://localhost:8086"

    def test_influxdb_settings_client_params(self):
        """Test client_params property."""
        settings = InfluxDBSettings(
            host="http://localhost",
            port=8086,
            token="my_token",
            org="my_org",
        )

        params = settings.client_params

        assert params["url"] == "http://localhost:8086"
        assert params["token"] == "my_token"
        assert params["org"] == "my_org"

    def test_influxdb_settings_is_configured_true(self):
        """Test is_configured returns True when all required fields set."""
        settings = InfluxDBSettings(
            host="localhost",
            port=8086,
            token="my_token",
            org="my_org",
        )

        assert settings.is_configured is True

    def test_influxdb_settings_is_configured_false_no_host(self):
        """Test is_configured returns False without host."""
        settings = InfluxDBSettings(
            token="my_token",
            org="my_org",
        )

        assert settings.is_configured is False

    def test_influxdb_settings_is_configured_false_no_token(self):
        """Test is_configured returns False without token."""
        settings = InfluxDBSettings(
            host="localhost",
            org="my_org",
        )

        assert settings.is_configured is False

    def test_influxdb_settings_is_configured_false_no_org(self):
        """Test is_configured returns False without org."""
        settings = InfluxDBSettings(
            host="localhost",
            token="my_token",
        )

        assert settings.is_configured is False

    def test_influxdb_settings_token_is_secret(self):
        """Test that token is a SecretStr."""
        settings = InfluxDBSettings(token="my_secret_token")

        assert isinstance(settings.token, SecretStr)
        assert str(settings.token) != "my_secret_token"  # Should be masked
