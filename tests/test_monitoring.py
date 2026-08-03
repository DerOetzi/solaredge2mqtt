"""Tests for monitoring.py top-level single-shot script."""

import runpy
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import ConfigurationException

WORKSPACE_ROOT = Path(__file__).parent.parent


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.monitoring.is_configured = True
    return settings


class TestMonitoringRun:
    """Tests for monitoring.run() error handling."""

    def test_run_invokes_run_coroutine_with_config_dir(self):
        import monitoring

        with patch("monitoring._run", new=AsyncMock()) as mock_run_coro:
            monitoring.run(config_dir="custom")

        mock_run_coro.assert_called_once_with("custom")

    def test_run_swallows_configuration_exception(self):
        import monitoring

        with (
            patch(
                "monitoring._run",
                new=AsyncMock(side_effect=ConfigurationException("x", "y")),
            ),
            patch("monitoring.logger") as mock_logger,
        ):
            monitoring.run()

        mock_logger.error.assert_called_once()

    def test_run_swallows_keyboard_interrupt(self):
        import monitoring

        with (
            patch("monitoring._run", new=AsyncMock(side_effect=KeyboardInterrupt())),
            patch("monitoring.logger") as mock_logger,
        ):
            monitoring.run()

        mock_logger.info.assert_called_once()


class TestMonitoringMain:
    """Tests for monitoring.main() argument parsing."""

    def test_main_with_default_config_dir(self):
        import monitoring

        with patch("monitoring.run") as mock_run:
            with patch.object(sys, "argv", ["monitoring.py"]):
                monitoring.main()

            mock_run.assert_called_once_with(config_dir="config")

    def test_main_with_custom_config_dir(self):
        import monitoring

        with patch("monitoring.run") as mock_run:
            with patch.object(
                sys, "argv", ["monitoring.py", "--config-dir", "/custom/config"]
            ):
                monitoring.main()

            mock_run.assert_called_once_with(config_dir="/custom/config")

    def test_main_guard_executes_module(self):
        """Executing script as __main__ should invoke main() guard path.

        runpy re-executes the file in a fresh namespace, so patches must
        target the source modules monitoring.py imports from (not the
        already-imported `monitoring` module) to actually take effect.
        """
        mock_settings = MagicMock()
        mock_settings.logging_level.level = "INFO"
        mock_settings.monitoring.is_configured = False

        with (
            patch(
                "solaredge2mqtt.core.settings.service_settings",
                return_value=mock_settings,
            ),
            patch("solaredge2mqtt.core.logging.initialize_logging"),
            patch.object(sys, "argv", ["monitoring.py"]),
        ):
            runpy.run_path(str(WORKSPACE_ROOT / "monitoring.py"), run_name="__main__")


class TestMonitoringRunInternal:
    """Tests for monitoring._run() orchestration logic."""

    @pytest.mark.asyncio
    async def test_not_configured_logs_error_and_returns(self, mock_settings):
        import monitoring

        mock_settings.monitoring.is_configured = False

        with (
            patch("monitoring.service_settings", return_value=mock_settings),
            patch("monitoring.initialize_logging"),
            patch("monitoring.logger") as mock_logger,
            patch("monitoring.MonitoringSite") as mock_site_cls,
        ):
            await monitoring._run("config")

        mock_logger.error.assert_called_once()
        mock_site_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_configured_fetches_and_logs_modules(self, mock_settings):
        import monitoring

        mock_module_with_power = MagicMock()
        mock_module_with_power.energy = 123.0
        mock_module_with_power.power = {"a": 1.0, "b": 2.0}

        mock_module_without_power = MagicMock()
        mock_module_without_power.energy = None
        mock_module_without_power.power = None

        mock_site = MagicMock()
        mock_site.get_modules = AsyncMock(
            return_value={
                "PAN1": mock_module_with_power,
                "PAN2": mock_module_without_power,
            }
        )
        mock_site.close = AsyncMock()

        with (
            patch("monitoring.service_settings", return_value=mock_settings),
            patch("monitoring.initialize_logging"),
            patch("monitoring.MonitoringSite", return_value=mock_site) as mock_site_cls,
        ):
            await monitoring._run("config")

        mock_site_cls.assert_called_once_with(mock_settings.monitoring, None)
        mock_site.get_modules.assert_called_once()
        mock_site.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_site_even_when_get_modules_raises(self, mock_settings):
        import monitoring

        mock_site = MagicMock()
        mock_site.get_modules = AsyncMock(side_effect=RuntimeError("boom"))
        mock_site.close = AsyncMock()

        with (
            patch("monitoring.service_settings", return_value=mock_settings),
            patch("monitoring.initialize_logging"),
            patch("monitoring.MonitoringSite", return_value=mock_site),
            pytest.raises(RuntimeError),
        ):
            await monitoring._run("config")

        mock_site.close.assert_called_once()
