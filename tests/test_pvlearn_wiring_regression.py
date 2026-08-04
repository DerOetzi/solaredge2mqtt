"""Phase 1a's solaredge2mqtt-side acceptance proof.

pvlearn's own regression test already proves the extracted Forecaster
reproduces the frozen Phase 0 baseline's predictive quality. This test proves
the wiring on top of it: that ForecastService correctly translates
LocationSettings/ForecastSettings into pvlearn's Location/ForecasterConfig,
and that Forecast inheriting from pvlearn.ForecastResult doesn't change what
gets predicted.

Tolerance, not exact equality, for the same reason as on the pvlearn side:
HistGradientBoostingRegressor's split search is sensitive to
CPU-microarchitecture floating point rounding, so bit-identical predictions
only hold on the machine that trained them.
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

FIXTURES_DIR = Path(__file__).parent / "fixtures"

RELATIVE_MAE_TOLERANCE = 0.10
ABSOLUTE_R2_TOLERANCE = 0.05
WH_PER_KWH = 1000

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
) -> dict[str, dict[str, float]]:
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

        metrics: dict[str, dict[str, float]] = {}
        for typed, forecaster in service.forecasters.items():
            assert forecaster.model_pipeline is not None
            predicted = forecaster.model_pipeline.predict(holdout_data)
            published = pd.Series(predicted).apply(typed.prepare_value)

            scale = WH_PER_KWH if typed.target_column == "energy" else 1
            actual = holdout_data[typed.target_column].to_numpy()
            comparable = published.to_numpy() * scale

            metrics[typed.target_column] = {
                "mae": float(mean_absolute_error(actual, comparable)),
                "r2": float(r2_score(actual, comparable)),
            }

    return metrics


class TestPvlearnWiringReproducesBaseline:
    @pytest.mark.parametrize("target", ["energy", "power"])
    def test_mae_matches_baseline_within_tolerance(
        self, target: str, wired_metrics: dict, baseline_metadata: dict
    ):
        wired_mae = wired_metrics[target]["mae"]
        baseline_mae = baseline_metadata["metrics"][target]["mae"]

        assert wired_mae == pytest.approx(baseline_mae, rel=RELATIVE_MAE_TOLERANCE)

    @pytest.mark.parametrize("target", ["energy", "power"])
    def test_r2_matches_baseline_within_tolerance(
        self, target: str, wired_metrics: dict, baseline_metadata: dict
    ):
        wired_r2 = wired_metrics[target]["r2"]
        baseline_r2 = baseline_metadata["metrics"][target]["r2"]

        assert wired_r2 == pytest.approx(baseline_r2, abs=ABSOLUTE_R2_TOLERANCE)
