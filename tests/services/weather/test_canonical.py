"""Tests for the OpenWeatherMap -> canonical schema translation."""

import pytest
from pvlearn.schema import (
    CATEGORICAL_FEATURES,
    CYCLICAL_FEATURES,
    NUMERIC_FEATURES,
)

from solaredge2mqtt.services.weather.canonical import (
    OPENWEATHERMAP_CONDITION_TO_WMO,
    OPENWEATHERMAP_TO_CANONICAL,
    UNKNOWN_CONDITION_WMO_CODE,
    to_canonical,
    to_wmo_code,
)

CANONICAL_FEATURES = (
    set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) | set(CYCLICAL_FEATURES)
)


class TestMapping:
    def test_every_target_is_a_canonical_feature(self):
        """A name pvlearn does not know would be silently ignored on training."""
        assert set(OPENWEATHERMAP_TO_CANONICAL.values()) <= CANONICAL_FEATURES

    def test_targets_are_unique(self):
        """Two provider fields mapping onto one feature would overwrite silently."""
        targets = list(OPENWEATHERMAP_TO_CANONICAL.values())
        assert len(targets) == len(set(targets))

    def test_irradiance_is_absent(self):
        """OpenWeatherMap delivers no irradiance, so those features stay empty."""
        mapped = set(OPENWEATHERMAP_TO_CANONICAL.values())

        assert not {"ghi", "dni", "dhi"} & mapped


class TestToWmoCode:
    @pytest.mark.parametrize(
        ("condition_id", "expected"),
        [
            (800, 0),
            (801, 1),
            (804, 3),
            (500, 61),
            (600, 71),
            (200, 95),
            (741, 45),
        ],
    )
    def test_known_conditions(self, condition_id: int, expected: int):
        assert to_wmo_code(condition_id) == expected

    def test_unknown_condition_becomes_overcast(self):
        assert to_wmo_code(999) == UNKNOWN_CONDITION_WMO_CODE

    def test_none_stays_none(self):
        """A missing condition must not turn into a made-up one."""
        assert to_wmo_code(None) is None

    def test_float_input_is_accepted(self):
        """InfluxDB returns numeric fields as floats."""
        assert to_wmo_code(800.0) == 0

    def test_all_codes_are_valid_wmo_values(self):
        assert all(0 <= code <= 99 for code in OPENWEATHERMAP_CONDITION_TO_WMO.values())


class TestToCanonical:
    def test_renames_known_fields(self):
        canonical = to_canonical(
            {
                "clouds": 20,
                "temp": 25.0,
                "wind_deg": 180,
                "pop": 0.1,
            }
        )

        assert canonical == {
            "cloud_cover": 20,
            "temperature": 25.0,
            "wind_direction": 180,
            "precipitation_probability": 0.1,
        }

    def test_drops_fields_without_counterpart(self):
        canonical = to_canonical({"weather_main": "Clear", "snow": 0.0, "temp": 25.0})

        assert canonical == {"temperature": 25.0}

    def test_translates_the_condition(self):
        assert to_canonical({"weather_id": 500}) == {"condition_code": 61}

    def test_non_numeric_condition_becomes_none(self):
        """A string where a code belongs is missing data, not overcast."""
        assert to_canonical({"weather_id": "Clear"}) == {"condition_code": None}

    def test_empty_input_yields_empty_output(self):
        assert to_canonical({}) == {}
