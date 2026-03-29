"""Tests for forecast __init__ module."""

import importlib
import sys

import pytest

from solaredge2mqtt.services.forecast import FORECAST_AVAILABLE, _deps_available


def _reload_forecast_module():
    """Reload forecast package to re-evaluate module-level availability logic."""
    sys.modules.pop("solaredge2mqtt.services.forecast", None)
    return importlib.import_module("solaredge2mqtt.services.forecast")


class TestForecastModule:
    """Tests for forecast module initialization."""

    def test_deps_available_returns_bool(self):
        """Test _deps_available returns a boolean."""
        result = _deps_available()

        assert isinstance(result, bool)

    def test_forecast_available_constant(self):
        """Test FORECAST_AVAILABLE constant is set."""
        assert isinstance(FORECAST_AVAILABLE, bool)

    def test_forecast_available_matches_deps(self):
        """Test FORECAST_AVAILABLE matches _deps_available."""
        assert FORECAST_AVAILABLE == _deps_available()

    def test_forecast_service_raises_when_optional_deps_missing(self, monkeypatch):
        """Test fallback ForecastService raises ImportError without forecast deps."""

        monkeypatch.setattr(
            "importlib.util.find_spec",
            lambda pkg: None,
        )

        forecast_module = _reload_forecast_module()

        assert forecast_module.FORECAST_AVAILABLE is False
        with pytest.raises(ImportError) as exc_info:
            forecast_module.ForecastService()

        assert "install extra dependencies" in str(exc_info.value)
