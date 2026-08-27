"""Tests for the provider independent weather models."""

from datetime import datetime, timezone

import pytest

from solaredge2mqtt.services.weather.models import (
    OpenWeatherMapCondition,
    OpenWeatherMapCurrentData,
    OpenWeatherMapForecastData,
    OpenWeatherMapOneCall,
)
from solaredge2mqtt.services.weather.result import WeatherResult, WeatherSnapshot

UTC_NOON = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)


def make_forecast_data(**overrides) -> OpenWeatherMapForecastData:
    """One OpenWeatherMap hourly entry."""
    values = {
        "dt": UTC_NOON,
        "temp": 25.0,
        "feels_like": 24.0,
        "humidity": 50,
        "clouds": 20,
        "pressure": 1013,
        "dew_point": 12.0,
        "visibility": 10000,
        "wind_speed": 5.0,
        "wind_gust": 8.0,
        "wind_deg": 180,
        "uvi": 5.0,
        "pop": 0.1,
        "weather": [
            OpenWeatherMapCondition(
                id=803, main="Clouds", description="broken clouds", icon="04d"
            )
        ],
    }
    values.update(overrides)
    return OpenWeatherMapForecastData(**values)


def make_one_call() -> OpenWeatherMapOneCall:
    """A One Call answer with a current snapshot and one hourly entry."""
    current = OpenWeatherMapCurrentData(
        dt=UTC_NOON,
        sunrise=UTC_NOON,
        sunset=UTC_NOON,
        temp=5.5,
        clouds=75,
        humidity=80,
        weather=[
            OpenWeatherMapCondition(
                id=800, main="Clear", description="clear sky", icon="01d"
            )
        ],
    )

    return OpenWeatherMapOneCall(
        lat=52.52,
        lon=13.405,
        timezone="Europe/Berlin",
        timezone_offset=3600,
        current=current,
        hourly=[make_forecast_data()],
    )


class TestToSnapshot:
    """Tests for translating a provider snapshot onto the canonical schema."""

    def test_renames_the_weather_fields(self):
        """Nothing behind the weather service sees the provider's names."""
        snapshot = make_forecast_data().to_snapshot()

        assert snapshot.temperature == pytest.approx(25.0)
        assert snapshot.cloud_cover == pytest.approx(20.0)
        assert snapshot.apparent_temperature == pytest.approx(24.0)
        assert snapshot.relative_humidity == pytest.approx(50.0)
        assert snapshot.surface_pressure == pytest.approx(1013.0)
        assert snapshot.wind_direction == pytest.approx(180.0)
        assert snapshot.precipitation_probability == pytest.approx(0.1)

    def test_translates_the_condition_to_wmo(self):
        """Broken clouds is WMO 3, overcast."""
        assert make_forecast_data().to_snapshot().condition_code == 3

    def test_stamps_the_provider(self):
        """Every snapshot states which provider it came from."""
        assert make_forecast_data().to_snapshot().weather_provider == "openweathermap"

    def test_truncates_the_time_to_the_hour(self):
        """Snapshots describe an hour, the model buckets them by it."""
        snapshot = make_forecast_data(
            dt=datetime(2024, 6, 15, 12, 34, 56, tzinfo=timezone.utc)
        ).to_snapshot()

        assert snapshot.time.minute == 0
        assert snapshot.time.second == 0

    def test_unset_features_stay_unset(self):
        """A provider that does not deliver irradiance leaves it empty."""
        snapshot = make_forecast_data().to_snapshot()

        assert snapshot.ghi is None
        assert snapshot.dni is None
        assert snapshot.dhi is None


class TestSnapshotHelpers:
    """Tests for the local time helpers the forecast service buckets by."""

    def test_local_parts(self):
        snapshot = make_forecast_data().to_snapshot()
        local = snapshot.localtime

        assert (snapshot.year, snapshot.month, snapshot.day, snapshot.hour) == (
            local.year,
            local.month,
            local.day,
            local.hour,
        )

    def test_model_dump_canonical_drops_time_and_timestamp(self):
        """The frame carries its own time column, the dump holds the features."""
        dumped = make_forecast_data().to_snapshot().model_dump_canonical()

        assert "time" not in dumped
        assert "timestamp" not in dumped
        assert dumped["temperature"] == pytest.approx(25.0)
        assert dumped["weather_provider"] == "openweathermap"

    def test_model_dump_canonical_drops_unset_features(self):
        """pvlearn tolerates a smaller feature set, not a set full of None."""
        dumped = make_forecast_data().to_snapshot().model_dump_canonical()

        assert "ghi" not in dumped

    def test_serializes_the_time_as_local_iso(self):
        """The published payload carries the local time of the interval."""
        snapshot = make_forecast_data().to_snapshot()

        assert snapshot.model_dump()["time"] == snapshot.localtime.isoformat()


class TestToResult:
    """Tests for translating a whole provider answer."""

    def test_translates_current_and_hourly(self):
        result = make_one_call().to_result()

        assert isinstance(result, WeatherResult)
        assert isinstance(result.current, WeatherSnapshot)
        assert result.current.temperature == pytest.approx(5.5)
        assert result.hourly[0].temperature == pytest.approx(25.0)

    def test_names_the_provider(self):
        assert make_one_call().to_result().weather_provider == "openweathermap"

    def test_drops_the_provider_specific_envelope(self):
        """Coordinates and timezone offsets are the adapter's business."""
        result = make_one_call().to_result()

        assert not hasattr(result, "lat")
        assert not hasattr(result, "timezone_offset")
