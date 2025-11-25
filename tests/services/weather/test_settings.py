"""Tests for weather settings module."""

from pydantic import SecretStr

from solaredge2mqtt.services.weather.settings import WeatherSettings


class TestWeatherSettings:
    """Tests for WeatherSettings class."""

    def test_weather_settings_defaults(self):
        """Test WeatherSettings default values."""
        settings = WeatherSettings()

        assert settings.api_key is None
        assert settings.language == "en"
        assert settings.retain is False

    def test_weather_settings_custom_values(self):
        """Test WeatherSettings with custom values."""
        settings = WeatherSettings(
            api_key="test_api_key_123",
            language="de",
            retain=True,
        )

        assert settings.api_key.get_secret_value() == "test_api_key_123"
        assert settings.language == "de"
        assert settings.retain is True

    def test_weather_settings_is_configured_true(self):
        """Test is_configured returns True when api_key is set."""
        settings = WeatherSettings(api_key="test_api_key")

        assert settings.is_configured is True

    def test_weather_settings_is_configured_false(self):
        """Test is_configured returns False when api_key is not set."""
        settings = WeatherSettings()

        assert settings.is_configured is False

    def test_weather_settings_api_key_is_secret(self):
        """Test that api_key is a SecretStr."""
        settings = WeatherSettings(api_key="my_secret_key")

        assert isinstance(settings.api_key, SecretStr)
        assert str(settings.api_key) != "my_secret_key"  # Should be masked

    def test_weather_settings_language_options(self):
        """Test various language options."""
        for lang in ["en", "de", "fr", "es", "it"]:
            settings = WeatherSettings(language=lang)
            assert settings.language == lang
