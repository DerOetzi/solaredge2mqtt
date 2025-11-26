"""Tests for forecast __init__ module."""

from solaredge2mqtt.services.forecast import FORECAST_AVAILABLE, _deps_available


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
