"""Regression tests for running without the optional forecast extra (#474)."""

import importlib
import subprocess
import sys
import textwrap
from unittest.mock import patch

import pytest

import solaredge2mqtt.services.homeassistant.service as ha_service
from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.monitoring.events import EVChargerReadEvent
from solaredge2mqtt.services.wallbox.events import WallboxReadEvent

_BLOCK_PVLEARN = textwrap.dedent(
    """
    import sys

    sys.modules["pvlearn"] = None
    """
)


def _run_without_pvlearn(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _BLOCK_PVLEARN + textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_service_imports_without_pvlearn():
    """The main service module must import when pvlearn is not installed."""
    result = _run_without_pvlearn(
        """
        import solaredge2mqtt.__main__
        from solaredge2mqtt.services.forecast import FORECAST_AVAILABLE

        assert FORECAST_AVAILABLE is False
        """
    )

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("forecast_available", [True, False])
def test_homeassistant_forecast_subscription_follows_availability(
    forecast_available: bool,
):
    """Home Assistant discovery subscribes to forecasts only when available."""
    try:
        with patch(
            "solaredge2mqtt.services.forecast.FORECAST_AVAILABLE", forecast_available
        ):
            module = importlib.reload(ha_service)

        subscribed = getattr(
            module.HomeAssistantDiscovery.component_discovery, "_event_subscriptions"
        )
        assert (ForecastEvent in subscribed) is forecast_available
        assert {EnergyReadEvent, WallboxReadEvent, EVChargerReadEvent} <= set(
            subscribed
        )
    finally:
        importlib.reload(ha_service)
