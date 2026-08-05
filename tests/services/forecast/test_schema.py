"""Tests for translating stored training data onto the canonical schema."""

from datetime import datetime, timezone

import pytest
from pandas import DataFrame, isna

from solaredge2mqtt.services.forecast.schema import to_canonical_frame


def make_training_frame(**overrides) -> DataFrame:
    """A row as `training_data.flux` returns it, under provider field names."""
    row = {
        "_time": [datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)],
        "time": [datetime(2024, 6, 15, 14, 0, tzinfo=timezone.utc)],
        "energy": [1500.0],
        "power": [1500.0],
        "clouds": [20.0],
        "temp": [25.0],
        "wind_deg": [180.0],
        "weather_id": [800.0],
        "weather_main": ["Clear"],
    }
    row.update({key: [value] for key, value in overrides.items()})
    return DataFrame(row)


class TestToCanonicalFrame:
    def test_keeps_time_and_target_under_their_own_names(self):
        canonical = to_canonical_frame(make_training_frame())

        assert "time" in canonical.columns
        assert canonical["energy"].iloc[0] == pytest.approx(1500.0)

    def test_renames_weather_columns(self):
        canonical = to_canonical_frame(make_training_frame())

        assert canonical["cloud_cover"].iloc[0] == pytest.approx(20.0)
        assert canonical["temperature"].iloc[0] == pytest.approx(25.0)
        assert canonical["wind_direction"].iloc[0] == pytest.approx(180.0)

    def test_translates_the_condition_to_wmo(self):
        canonical = to_canonical_frame(make_training_frame())

        assert canonical["condition_code"].iloc[0] == 0

    def test_drops_columns_without_counterpart(self):
        canonical = to_canonical_frame(make_training_frame())

        assert "power" not in canonical.columns
        assert "_time" not in canonical.columns
        assert "weather_main" not in canonical.columns

    def test_missing_columns_are_not_invented(self):
        """History predating a field simply lacks it."""
        data = make_training_frame().drop(columns=["temp", "weather_id"])

        canonical = to_canonical_frame(data)

        assert "temperature" not in canonical.columns
        assert "condition_code" not in canonical.columns

    def test_missing_condition_value_stays_missing(self):
        canonical = to_canonical_frame(make_training_frame(weather_id=None))

        assert isna(canonical["condition_code"].iloc[0])

    def test_input_frame_is_not_modified(self):
        data = make_training_frame()

        to_canonical_frame(data)

        assert data["weather_id"].iloc[0] == pytest.approx(800.0)
        assert "clouds" in data.columns
