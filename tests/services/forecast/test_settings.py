"""Tests for forecast settings module."""


from solaredge2mqtt.services.forecast.settings import ForecastSettings

# Note: ForecastSettings.ensure_secure_cache validator has a pydantic v1/v2
# compatibility issue (uses `values.get()` instead of `info.data.get()`).
# This limits test coverage for cachingdir=None scenarios.
# See: https://docs.pydantic.dev/latest/migration/#field-validators


class TestForecastSettings:
    """Tests for ForecastSettings class."""

    def test_forecast_settings_defaults(self):
        """Test ForecastSettings default values."""
        settings = ForecastSettings()

        assert settings.enable is False
        assert settings.hyperparametertuning is False
        assert settings.retain is False

    def test_forecast_settings_is_configured_false(self):
        """Test is_configured returns False when disabled."""
        settings = ForecastSettings(enable=False)

        assert settings.is_configured is False

    def test_forecast_settings_is_caching_enabled_with_default(self):
        """Test is_caching_enabled with default cachingdir."""
        settings = ForecastSettings()

        # Default cachingdir is set to user cache dir
        assert settings.is_caching_enabled is True

    def test_forecast_settings_hyperparametertuning_flag(self):
        """Test hyperparametertuning flag."""
        settings_false = ForecastSettings(hyperparametertuning=False)
        settings_true = ForecastSettings(hyperparametertuning=True)

        assert settings_false.hyperparametertuning is False
        assert settings_true.hyperparametertuning is True

    def test_forecast_settings_retain_flag(self):
        """Test retain flag."""
        settings_false = ForecastSettings(retain=False)
        settings_true = ForecastSettings(retain=True)

        assert settings_false.retain is False
        assert settings_true.retain is True

    def test_forecast_settings_enable_flag(self):
        """Test enable flag."""
        settings_false = ForecastSettings(enable=False)
        settings_true = ForecastSettings(enable=True)

        assert settings_false.enable is False
        assert settings_true.enable is True
