"""Verifies ForecastService's wiring into pvlearn against the frozen baseline.

Retrains through LocationSettings/ForecastSettings -> pvlearn.Location/
ForecasterConfig and checks the resulting predictions' MAE/R² against
tests/fixtures/baseline_forecast.json within tolerance. See
docs/decisions/0001-pvlearn-extraction-wiring.md for why.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from sklearn.metrics import mean_absolute_error, r2_score

from solaredge2mqtt.core.settings.models import LocationSettings
from solaredge2mqtt.services.forecast.service import ForecastService
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.weather.models import OpenWeatherMapBaseData

FIXTURES_DIR = Path(__file__).parent / "fixtures"

RELATIVE_MAE_TOLERANCE = 0.10
ABSOLUTE_R2_TOLERANCE = 0.05

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def reference_metadata() -> dict:
    return json.loads((FIXTURES_DIR / "reference_dataset.json").read_text())


@pytest.fixture(scope="module")
def baseline_metadata() -> dict:
    return json.loads((FIXTURES_DIR / "baseline_forecast.json").read_text())


@pytest.fixture(scope="module")
def reference_dataset() -> pd.DataFrame:
    data = pd.read_parquet(FIXTURES_DIR / "reference_dataset.parquet")
    return data.sort_values("_time").reset_index(drop=True)


@pytest.fixture(scope="module")
def wired_metrics(
    reference_dataset: pd.DataFrame,
    reference_metadata: dict,
    baseline_metadata: dict,
) -> dict[str, float]:
    location_data = reference_metadata["location"]
    timezone = ZoneInfo(location_data["timezone"])

    data = reference_dataset.copy()
    data["time"] = data["_time"].dt.tz_convert(timezone)

    holdout = baseline_metadata["holdout_rows"]
    train_data = data.iloc[:-holdout]
    holdout_data = data.iloc[-holdout:]

    location = LocationSettings(
        latitude=location_data["latitude"],
        longitude=location_data["longitude"],
    )
    settings = ForecastSettings(enable=False, hyperparametertuning=False)

    with patch("solaredge2mqtt.services.forecast.service.LOCAL_TZ", timezone):
        service = ForecastService(settings, location, influxdb=MagicMock())
        service.training(train_data)

        forecaster = service.forecaster
        assert forecaster.model_pipeline is not None

        predicted = forecaster.model_pipeline.predict(
            OpenWeatherMapBaseData.to_canonical_frame(holdout_data)
        )
        published = pd.Series(predicted).apply(forecaster.prepare_value)

    # Both sides are Wh: the stored `energy` field has always been, and pvlearn
    # publishes Wh since 0.2.0 instead of dividing by 1000 on the way out.
    actual = holdout_data["energy"].to_numpy()
    comparable = published.to_numpy()

    return {
        "mae": float(mean_absolute_error(actual, comparable)),
        "r2": float(r2_score(actual, comparable)),
    }


class TestPvlearnWiringReproducesBaseline:
    def test_mae_matches_baseline_within_tolerance(
        self, wired_metrics: dict, baseline_metadata: dict
    ):
        baseline_mae = baseline_metadata["metrics"]["energy"]["mae"]

        assert wired_metrics["mae"] == pytest.approx(
            baseline_mae, rel=RELATIVE_MAE_TOLERANCE
        )

    def test_r2_matches_baseline_within_tolerance(
        self, wired_metrics: dict, baseline_metadata: dict
    ):
        baseline_r2 = baseline_metadata["metrics"]["energy"]["r2"]

        assert wired_metrics["r2"] == pytest.approx(
            baseline_r2, abs=ABSOLUTE_R2_TOLERANCE
        )
