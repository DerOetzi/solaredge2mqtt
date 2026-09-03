"""Tests for forecast.py top-level standalone-run script."""

import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pandas import DataFrame

from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException

WORKSPACE_ROOT = Path(__file__).parent.parent


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.logging_level.level = "INFO"
    settings.is_forecast_enabled = True
    settings.storage.is_configured = True
    return settings


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.async_init = AsyncMock()
    storage.close = AsyncMock()
    return storage


@pytest.fixture
def mock_weather():
    weather = MagicMock()
    weather.get_weather = AsyncMock(return_value=MagicMock())
    weather.close = AsyncMock()
    return weather


@pytest.fixture
def mock_forecast_service():
    service = MagicMock()
    service.weather_update = AsyncMock()
    service.train = AsyncMock()
    service.predict_elapsed_today = AsyncMock(
        return_value=DataFrame({"time": [], "energy": []})
    )
    service.predict = AsyncMock(
        return_value=DataFrame(
            {
                "time": [datetime(2024, 1, 1, 12, tzinfo=timezone.utc)],
                "energy": [1500.0],
            }
        )
    )
    service.battery_charge_needed_wh = MagicMock(return_value=2000.0)
    return service


class TestEnergyPeriod:
    """Tests for forecast._energy_period()."""

    def test_builds_dict_from_valid_rows(self):
        import forecast

        predictions = DataFrame(
            {
                "time": [
                    datetime(2024, 1, 1, 10, tzinfo=timezone.utc),
                    datetime(2024, 1, 1, 11, tzinfo=timezone.utc),
                ],
                "energy": [100.4, 200.6],
            }
        )

        result = forecast._energy_period(predictions)

        assert result == {
            datetime(2024, 1, 1, 10, tzinfo=timezone.utc): 100,
            datetime(2024, 1, 1, 11, tzinfo=timezone.utc): 201,
        }

    def test_raises_on_invalid_time(self):
        import forecast

        predictions = DataFrame({"time": ["not-a-datetime"], "energy": [100.0]})

        with pytest.raises(InvalidDataException):
            forecast._energy_period(predictions)

    def test_raises_on_invalid_energy(self):
        import forecast

        predictions = DataFrame(
            {"time": [datetime(2024, 1, 1, tzinfo=timezone.utc)], "energy": ["bad"]}
        )

        with pytest.raises(InvalidDataException):
            forecast._energy_period(predictions)


class TestForecastRun:
    """Tests for forecast.run() error handling."""

    def test_run_invokes_run_coroutine_with_args(self):
        import forecast

        with patch("forecast._run", new=AsyncMock()) as mock_run_coro:
            forecast.run(
                config_dir="custom", battery_capacity_wh=9200.0, battery_soc=50.0
            )

        mock_run_coro.assert_called_once_with("custom", 9200.0, 50.0)

    def test_run_swallows_configuration_exception(self):
        import forecast

        with (
            patch(
                "forecast._run",
                new=AsyncMock(side_effect=ConfigurationException("x", "y")),
            ),
            patch("forecast.logger") as mock_logger,
        ):
            forecast.run()

        mock_logger.error.assert_called_once()

    def test_run_swallows_invalid_data_exception(self):
        import forecast

        with (
            patch(
                "forecast._run",
                new=AsyncMock(side_effect=InvalidDataException("bad row")),
            ),
            patch("forecast.logger") as mock_logger,
        ):
            forecast.run()

        mock_logger.error.assert_called_once()

    def test_run_swallows_keyboard_interrupt(self):
        import forecast

        with (
            patch("forecast._run", new=AsyncMock(side_effect=KeyboardInterrupt())),
            patch("forecast.logger") as mock_logger,
        ):
            forecast.run()

        mock_logger.info.assert_called_once()


class TestForecastMain:
    """Tests for forecast.main() argument parsing."""

    def test_main_with_default_args(self):
        import forecast

        with patch("forecast.run") as mock_run:
            with patch.object(sys, "argv", ["forecast.py"]):
                forecast.main()

            mock_run.assert_called_once_with(
                config_dir="config", battery_capacity_wh=None, battery_soc=None
            )

    def test_main_with_custom_args(self):
        import forecast

        with patch("forecast.run") as mock_run:
            with patch.object(
                sys,
                "argv",
                [
                    "forecast.py",
                    "--config-dir",
                    "/custom/config",
                    "--battery-capacity-wh",
                    "9200",
                    "--battery-soc",
                    "60",
                ],
            ):
                forecast.main()

            mock_run.assert_called_once_with(
                config_dir="/custom/config",
                battery_capacity_wh=9200.0,
                battery_soc=60.0,
            )

    def test_main_guard_executes_module(self):
        """Executing the script as __main__ should invoke main() guard path.

        runpy re-executes the file in a fresh namespace, so patches must
        target the source modules forecast.py imports from (not the
        already-imported `forecast` module) to actually take effect.
        """
        mock_settings = MagicMock()
        mock_settings.logging_level.level = "INFO"
        mock_settings.is_forecast_enabled = False

        with (
            patch(
                "solaredge2mqtt.core.settings.service_settings",
                return_value=mock_settings,
            ),
            patch("solaredge2mqtt.core.logging.initialize_logging"),
            patch.object(sys, "argv", ["forecast.py"]),
        ):
            runpy.run_path(str(WORKSPACE_ROOT / "forecast.py"), run_name="__main__")


class TestForecastRunInternal:
    """Tests for forecast._run() orchestration logic."""

    @pytest.mark.asyncio
    async def test_forecast_not_available_logs_error_and_returns(self, mock_settings):
        import forecast

        with (
            patch("forecast.service_settings", return_value=mock_settings),
            patch("forecast.initialize_logging"),
            patch("forecast.FORECAST_AVAILABLE", False),
            patch("forecast.logger") as mock_logger,
            patch("forecast.StorageService") as mock_storage_cls,
        ):
            await forecast._run("config", None, None)

        mock_logger.error.assert_called_once()
        mock_storage_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_forecast_not_enabled_logs_error_and_returns(self, mock_settings):
        import forecast

        mock_settings.is_forecast_enabled = False

        with (
            patch("forecast.service_settings", return_value=mock_settings),
            patch("forecast.initialize_logging"),
            patch("forecast.logger") as mock_logger,
            patch("forecast.StorageService") as mock_storage_cls,
        ):
            await forecast._run("config", None, None)

        mock_logger.error.assert_called_once()
        mock_storage_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_storage_not_configured_logs_error_and_returns(self, mock_settings):
        import forecast

        mock_settings.storage.is_configured = False

        with (
            patch("forecast.service_settings", return_value=mock_settings),
            patch("forecast.initialize_logging"),
            patch("forecast.logger") as mock_logger,
            patch("forecast.StorageService") as mock_storage_cls,
        ):
            await forecast._run("config", None, None)

        mock_logger.error.assert_called_once()
        mock_storage_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_run_without_battery_args(
        self, mock_settings, mock_storage, mock_weather, mock_forecast_service
    ):
        import forecast

        with (
            patch("forecast.service_settings", return_value=mock_settings),
            patch("forecast.initialize_logging"),
            patch("forecast.StorageService", return_value=mock_storage),
            patch("forecast.WeatherClient", return_value=mock_weather),
            patch(
                "forecast.ForecastService", return_value=mock_forecast_service
            ) as mock_service_cls,
        ):
            await forecast._run("config", None, None)

        mock_service_cls.assert_called_once_with(
            mock_settings.forecast, mock_settings.location, mock_storage
        )
        mock_forecast_service.weather_update.assert_called_once()
        mock_forecast_service.train.assert_called_once()
        mock_forecast_service.battery_charge_needed_wh.assert_not_called()
        mock_weather.close.assert_called_once()
        mock_storage.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_run_with_battery_args(
        self, mock_settings, mock_storage, mock_weather, mock_forecast_service
    ):
        import forecast

        with (
            patch("forecast.service_settings", return_value=mock_settings),
            patch("forecast.initialize_logging"),
            patch("forecast.StorageService", return_value=mock_storage),
            patch("forecast.WeatherClient", return_value=mock_weather),
            patch("forecast.ForecastService", return_value=mock_forecast_service),
        ):
            await forecast._run("config", 9200.0, 50.0)

        assert mock_forecast_service.last_battery_capacity_wh == 9200.0
        assert mock_forecast_service.last_battery_stored_energy_wh == 4600.0
        mock_forecast_service.battery_charge_needed_wh.assert_called_once()
        mock_weather.close.assert_called_once()
        mock_storage.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_weather_and_storage_even_when_train_raises(
        self, mock_settings, mock_storage, mock_weather, mock_forecast_service
    ):
        import forecast

        mock_forecast_service.train = AsyncMock(side_effect=RuntimeError("boom"))

        with (
            patch("forecast.service_settings", return_value=mock_settings),
            patch("forecast.initialize_logging"),
            patch("forecast.StorageService", return_value=mock_storage),
            patch("forecast.WeatherClient", return_value=mock_weather),
            patch("forecast.ForecastService", return_value=mock_forecast_service),
            pytest.raises(RuntimeError),
        ):
            await forecast._run("config", None, None)

        mock_weather.close.assert_called_once()
        mock_storage.close.assert_called_once()
