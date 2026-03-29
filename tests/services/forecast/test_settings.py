"""Tests for forecast settings module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from solaredge2mqtt.services.forecast.settings import (
    ForecastSettings,
    _get_default_cache_dir,
)

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

    def test_default_cache_dir_in_docker_via_file(self):
        """Docker environments should use /app/cache."""
        with patch(
            "solaredge2mqtt.services.forecast.settings.Path.exists",
            return_value=True,
        ):
            assert _get_default_cache_dir() == "/app/cache"

    def test_default_cache_dir_in_docker_via_env(self):
        """DOCKER_CONTAINER=true should force docker cache path."""
        with (
            patch(
                "solaredge2mqtt.services.forecast.settings.Path.exists",
                return_value=False,
            ),
            patch(
                "solaredge2mqtt.services.forecast.settings.getenv",
                return_value="true",
            ),
        ):
            assert _get_default_cache_dir() == "/app/cache"

    def test_default_cache_dir_non_docker_uses_platformdirs(self):
        """Non-docker environments should use platform cache dir."""
        with (
            patch(
                "solaredge2mqtt.services.forecast.settings.Path.exists",
                return_value=False,
            ),
            patch(
                "solaredge2mqtt.services.forecast.settings.getenv",
                return_value=None,
            ),
            patch(
                "solaredge2mqtt.services.forecast.settings.platformdirs.user_cache_dir",
                return_value="/tmp/cache",  # noqa: S5443
            ),
        ):
            assert _get_default_cache_dir() == "/tmp/cache"  # noqa: S5443

    def test_ensure_secure_cache_returns_none_when_disabled(self):
        """Caching directory should be disabled when forecast is disabled."""
        settings = ForecastSettings(enable=False, cachingdir="/tmp/forecast-cache")  # noqa: S5443

        assert settings.cachingdir is None

    def test_ensure_secure_cache_creates_and_returns_secure_path(self, tmp_path):
        """Enabled forecast should keep secure cache directory."""
        secure_dir = tmp_path / "cache"

        with patch("solaredge2mqtt.services.forecast.settings.chmod") as chmod_mock:
            settings = ForecastSettings(enable=True, cachingdir=str(secure_dir))

        assert settings.cachingdir == str(Path(secure_dir).resolve())
        chmod_mock.assert_called_once()

    def test_ensure_secure_cache_rejects_insecure_permissions(self, tmp_path):
        """Insecure permissions should raise ValueError."""
        insecure_dir = tmp_path / "insecure-cache"

        with patch("solaredge2mqtt.services.forecast.settings.Path.stat") as stat_mock:
            stat_mock.return_value.st_mode = 0o777
            with pytest.raises(ValueError):
                ForecastSettings(enable=True, cachingdir=str(insecure_dir))
