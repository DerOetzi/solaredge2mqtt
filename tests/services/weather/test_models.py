"""Tests for weather models module."""

from datetime import datetime, timezone

import pytest
from pandas import DataFrame, concat, isna
from pvlearn.schema import (
    CATEGORICAL_FEATURES,
    CYCLICAL_FEATURES,
    NUMERIC_FEATURES,
)

from solaredge2mqtt.services.weather.models import (
    OpenWeatherMapBaseData,
    OpenWeatherMapCondition,
    OpenWeatherMapCurrentData,
    OpenWeatherMapForecastData,
    OpenWeatherMapOneCall,
    OpenWeatherMapOneCallBase,
    OpenWeatherMapRain,
    OpenWeatherMapSnow,
)

CANONICAL_FEATURES = (
    set(NUMERIC_FEATURES) | set(CATEGORICAL_FEATURES) | set(CYCLICAL_FEATURES)
)


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


def make_condition() -> dict:
    """Create weather condition data for testing."""
    return {
        "id": 800,
        "main": "Clear",
        "description": "clear sky",
        "icon": "01d",
    }


def make_base_data(dt: datetime | None = None) -> dict:
    """Create base weather data for testing."""
    return {
        "dt": dt or datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        "temp": 25.5,
        "feels_like": 26.0,
        "pressure": 1013,
        "humidity": 65,
        "dew_point": 18.5,
        "uvi": 7.5,
        "clouds": 10,
        "visibility": 10000,
        "wind_speed": 5.5,
        "wind_deg": 180,
        "wind_gust": 8.0,
        "weather": [make_condition()],
    }


class TestOpenWeatherMapRain:
    """Tests for OpenWeatherMapRain class."""

    def test_rain_default_value(self):
        """Test rain with default value."""
        rain = OpenWeatherMapRain()
        assert rain.one_hour == pytest.approx(0.0)

    def test_rain_with_value(self):
        """Test rain with value."""
        rain = OpenWeatherMapRain.model_validate({"1h": 2.5})
        assert rain.one_hour == pytest.approx(2.5)

    def test_rain_serialization(self):
        """Test rain serialization returns float."""
        rain = OpenWeatherMapRain.model_validate({"1h": 3.5})
        serialized = rain.model_dump()
        assert serialized == pytest.approx(3.5)


class TestOpenWeatherMapSnow:
    """Tests for OpenWeatherMapSnow class."""

    def test_snow_inherits_from_rain(self):
        """Test snow inherits from rain."""
        assert issubclass(OpenWeatherMapSnow, OpenWeatherMapRain)

    def test_snow_default_value(self):
        """Test snow with default value."""
        snow = OpenWeatherMapSnow()
        assert snow.one_hour == pytest.approx(0.0)

    def test_snow_with_value(self):
        """Test snow with value."""
        snow = OpenWeatherMapSnow.model_validate({"1h": 1.5})
        assert snow.one_hour == pytest.approx(1.5)


class TestOpenWeatherMapCondition:
    """Tests for OpenWeatherMapCondition class."""

    def test_condition_creation(self):
        """Test condition creation."""
        condition = OpenWeatherMapCondition(**make_condition())

        assert condition.id == 800
        assert condition.main == "Clear"
        assert condition.description == "clear sky"
        assert condition.icon == "01d"


class TestOpenWeatherMapBaseData:
    """Tests for OpenWeatherMapBaseData class."""

    def test_base_data_creation(self):
        """Test base data creation."""
        data = make_base_data()
        base = OpenWeatherMapBaseData(**data)

        assert base.temp == pytest.approx(25.5)
        assert base.feels_like == pytest.approx(26.0)
        assert base.pressure == 1013
        assert base.humidity == 65

    def test_base_data_localtime_property(self):
        """Test localtime property converts to local timezone."""
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = make_base_data(dt)
        base = OpenWeatherMapBaseData(**data)

        # localtime should be timezone-aware
        assert base.localtime.tzinfo is not None

    def test_base_data_year_property(self):
        """Test year property."""
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = make_base_data(dt)
        base = OpenWeatherMapBaseData(**data)

        assert base.year == 2024

    def test_base_data_month_property(self):
        """Test month property."""
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = make_base_data(dt)
        base = OpenWeatherMapBaseData(**data)

        assert base.month == 6

    def test_base_data_day_property(self):
        """Test day property."""
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = make_base_data(dt)
        base = OpenWeatherMapBaseData(**data)

        assert base.day == 15

    def test_base_data_hour_property(self):
        """Test hour property."""
        dt = datetime(2024, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        data = make_base_data(dt)
        base = OpenWeatherMapBaseData(**data)

        # Hour depends on local timezone
        assert isinstance(base.hour, int)

    def test_base_data_serialize_dt(self):
        """Test dt serialization to isoformat."""
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        data = make_base_data(dt)
        base = OpenWeatherMapBaseData(**data)

        dump = base.model_dump()
        assert isinstance(dump["dt"], str)

    def test_base_data_serialize_weather(self):
        """Test weather serialization returns first condition."""
        data = make_base_data()
        base = OpenWeatherMapBaseData(**data)

        dump = base.model_dump()
        # Weather should be serialized as the first condition object
        assert "weather" in dump
        assert dump["weather"]["main"] == "Clear"

    def test_base_data_model_dump_estimation_data(self):
        """Test model_dump_estimation_data method."""
        data = make_base_data()
        base = OpenWeatherMapBaseData(**data)

        estimation_data = base.model_dump_estimation_data()

        assert "weather_id" in estimation_data
        assert "weather_main" in estimation_data
        assert estimation_data["weather_id"] == 800
        assert estimation_data["weather_main"] == "Clear"
        # dt should be excluded
        assert "dt" not in estimation_data
        # weather should be excluded (replaced with weather_id, weather_main)
        assert "weather" not in estimation_data

    def test_base_data_model_dump_canonical(self):
        """model_dump_canonical renames onto pvlearn's schema and drops the rest."""
        data = make_base_data()
        base = OpenWeatherMapBaseData(**data)

        canonical = base.model_dump_canonical()

        assert canonical["cloud_cover"] == 10
        assert canonical["temperature"] == pytest.approx(25.5)
        assert canonical["relative_humidity"] == 65
        assert canonical["wind_direction"] == 180
        # 800 is OpenWeatherMap's clear sky, WMO code 0.
        assert canonical["condition_code"] == 0
        # No provider field survives under its own name.
        assert "clouds" not in canonical
        assert "weather_main" not in canonical

    def test_base_data_with_rain(self):
        """Test base data with rain."""
        data = make_base_data()
        data["rain"] = {"1h": 2.5}
        base = OpenWeatherMapBaseData(**data)

        assert base.rain.one_hour == pytest.approx(2.5)

    def test_base_data_with_snow(self):
        """Test base data with snow."""
        data = make_base_data()
        data["snow"] = {"1h": 1.0}
        base = OpenWeatherMapBaseData(**data)

        assert base.snow.one_hour == pytest.approx(1.0)


class TestOpenWeatherMapCurrentData:
    """Tests for OpenWeatherMapCurrentData class."""

    def test_current_data_creation(self):
        """Test current data creation."""
        data = make_base_data()
        data["sunrise"] = datetime(2024, 6, 15, 5, 30, 0, tzinfo=timezone.utc)
        data["sunset"] = datetime(2024, 6, 15, 21, 30, 0, tzinfo=timezone.utc)

        current = OpenWeatherMapCurrentData(**data)

        assert current.temp == pytest.approx(25.5)
        assert current.sunrise.hour == 5
        assert current.sunset.hour == 21


class TestOpenWeatherMapForecastData:
    """Tests for OpenWeatherMapForecastData class."""

    def test_forecast_data_creation(self):
        """Test forecast data creation."""
        data = make_base_data()
        data["pop"] = 0.25

        forecast = OpenWeatherMapForecastData(**data)

        assert forecast.temp == pytest.approx(25.5)
        assert forecast.pop == pytest.approx(0.25)


class TestOpenWeatherMapOneCallBase:
    """Tests for OpenWeatherMapOneCallBase class."""

    def test_one_call_base_creation(self):
        """Test one call base creation."""
        data = {
            "lat": 52.52,
            "lon": 13.405,
            "timezone": "Europe/Berlin",
            "timezone_offset": 7200,
        }

        base = OpenWeatherMapOneCallBase(**data)

        assert base.lat == pytest.approx(52.52)
        assert base.lon == pytest.approx(13.405)
        assert base.timezone == "Europe/Berlin"
        assert base.timezone_offset == 7200


class TestOpenWeatherMapOneCall:
    """Tests for OpenWeatherMapOneCall class."""

    def test_one_call_creation(self):
        """Test one call creation."""
        current_data = make_base_data()
        current_data["sunrise"] = datetime(2024, 6, 15, 5, 30, 0, tzinfo=timezone.utc)
        current_data["sunset"] = datetime(2024, 6, 15, 21, 30, 0, tzinfo=timezone.utc)

        forecast_data = make_base_data()
        forecast_data["pop"] = 0.1

        data = {
            "lat": 52.52,
            "lon": 13.405,
            "timezone": "Europe/Berlin",
            "timezone_offset": 7200,
            "current": current_data,
            "hourly": [forecast_data],
        }

        one_call = OpenWeatherMapOneCall(**data)

        assert one_call.lat == pytest.approx(52.52)
        assert one_call.current.temp == pytest.approx(25.5)
        assert len(one_call.hourly) == 1
        assert one_call.hourly[0].pop == pytest.approx(0.1)


class TestCanonicalMapping:
    """Tests for the OpenWeatherMap -> canonical schema mapping."""

    def test_every_target_is_a_canonical_feature(self):
        """A name pvlearn does not know would be silently ignored on training."""
        assert set(OpenWeatherMapBaseData.CANONICAL_FIELDS.values()) <= (
            CANONICAL_FEATURES
        )

    def test_targets_are_unique(self):
        """Two provider fields mapping onto one feature would overwrite silently."""
        targets = list(OpenWeatherMapBaseData.CANONICAL_FIELDS.values())
        assert len(targets) == len(set(targets))

    def test_irradiance_is_absent(self):
        """OpenWeatherMap delivers no irradiance, so those features stay empty."""
        mapped = set(OpenWeatherMapBaseData.CANONICAL_FIELDS.values())

        assert not {"ghi", "dni", "dhi"} & mapped

    def test_provider_field_is_a_canonical_categorical(self):
        """pvlearn learns the provider per row, so the name has to match."""
        assert OpenWeatherMapBaseData.PROVIDER_FIELD in CATEGORICAL_FEATURES

    def test_provider_is_not_read_off_the_payload(self):
        """The adapter stamps its own name; no provider field maps onto it."""
        assert OpenWeatherMapBaseData.PROVIDER_FIELD not in (
            OpenWeatherMapBaseData.CANONICAL_FIELDS.values()
        )


class TestToWmoCode:
    """Tests for translating condition ids to WMO codes."""

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
        assert OpenWeatherMapBaseData.to_wmo_code(condition_id) == expected

    def test_unknown_condition_becomes_overcast(self):
        assert (
            OpenWeatherMapBaseData.to_wmo_code(999)
            == OpenWeatherMapBaseData.UNKNOWN_CONDITION_WMO_CODE
        )

    def test_none_stays_none(self):
        """A missing condition must not turn into a made-up one."""
        assert OpenWeatherMapBaseData.to_wmo_code(None) is None

    def test_float_input_is_accepted(self):
        """InfluxDB returns numeric fields as floats."""
        assert OpenWeatherMapBaseData.to_wmo_code(800.0) == 0

    def test_all_codes_are_valid_wmo_values(self):
        assert all(
            0 <= code <= 99 for code in OpenWeatherMapBaseData.CONDITION_TO_WMO.values()
        )


class TestToCanonical:
    """Tests for translating one stored snapshot."""

    def test_renames_known_fields(self):
        canonical = OpenWeatherMapBaseData.to_canonical(
            {
                "clouds": 20,
                "temp": 25.0,
                "wind_deg": 180,
                "pop": 0.1,
            }
        )

        assert canonical == {
            "weather_provider": "openweathermap",
            "cloud_cover": 20,
            "temperature": 25.0,
            "wind_direction": 180,
            "precipitation_probability": 0.1,
        }

    def test_drops_fields_without_counterpart(self):
        canonical = OpenWeatherMapBaseData.to_canonical(
            {"weather_main": "Clear", "snow": 0.0, "temp": 25.0}
        )

        assert canonical == {
            "weather_provider": "openweathermap",
            "temperature": 25.0,
        }

    def test_translates_the_condition(self):
        canonical = OpenWeatherMapBaseData.to_canonical({"weather_id": 500})

        assert canonical == {
            "weather_provider": "openweathermap",
            "condition_code": 61,
        }

    def test_non_numeric_condition_becomes_none(self):
        """A string where a code belongs is missing data, not overcast."""
        canonical = OpenWeatherMapBaseData.to_canonical({"weather_id": "Clear"})

        assert canonical == {
            "weather_provider": "openweathermap",
            "condition_code": None,
        }

    def test_empty_input_yields_only_the_provider(self):
        """The provider is this adapter's own fact, not one of the payload's."""
        assert OpenWeatherMapBaseData.to_canonical({}) == {
            "weather_provider": "openweathermap"
        }


class TestToCanonicalFrame:
    """Tests for translating a stored `forecast_training` frame."""

    def test_keeps_time_and_target_under_their_own_names(self):
        canonical = OpenWeatherMapBaseData.to_canonical_frame(make_training_frame())

        assert "time" in canonical.columns
        assert canonical["energy"].iloc[0] == pytest.approx(1500.0)

    def test_renames_weather_columns(self):
        canonical = OpenWeatherMapBaseData.to_canonical_frame(make_training_frame())

        assert canonical["cloud_cover"].iloc[0] == pytest.approx(20.0)
        assert canonical["temperature"].iloc[0] == pytest.approx(25.0)
        assert canonical["wind_direction"].iloc[0] == pytest.approx(180.0)

    def test_translates_the_condition_to_wmo(self):
        canonical = OpenWeatherMapBaseData.to_canonical_frame(make_training_frame())

        assert canonical["condition_code"].iloc[0] == 0

    def test_drops_columns_without_counterpart(self):
        canonical = OpenWeatherMapBaseData.to_canonical_frame(make_training_frame())

        assert "power" not in canonical.columns
        assert "_time" not in canonical.columns
        assert "weather_main" not in canonical.columns

    def test_missing_columns_are_not_invented(self):
        """History predating a field simply lacks it."""
        data = make_training_frame().drop(columns=["temp", "weather_id"])

        canonical = OpenWeatherMapBaseData.to_canonical_frame(data)

        assert "temperature" not in canonical.columns
        assert "condition_code" not in canonical.columns

    def test_missing_condition_value_stays_missing(self):
        canonical = OpenWeatherMapBaseData.to_canonical_frame(
            make_training_frame(weather_id=None)
        )

        assert isna(canonical["condition_code"].iloc[0])

    def test_stamps_the_provider_onto_every_row(self):
        data = concat([make_training_frame(), make_training_frame()])

        canonical = OpenWeatherMapBaseData.to_canonical_frame(data)

        assert list(canonical["weather_provider"]) == ["openweathermap"] * 2

    def test_input_frame_is_not_modified(self):
        data = make_training_frame()

        OpenWeatherMapBaseData.to_canonical_frame(data)

        assert data["weather_id"].iloc[0] == pytest.approx(800.0)
        assert "clouds" in data.columns
