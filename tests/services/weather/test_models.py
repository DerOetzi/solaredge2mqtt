"""Tests for weather models module."""

from datetime import datetime, timezone

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
        assert rain.one_hour == 0.0

    def test_rain_with_value(self):
        """Test rain with value."""
        rain = OpenWeatherMapRain(**{"1h": 2.5})
        assert rain.one_hour == 2.5

    def test_rain_serialization(self):
        """Test rain serialization returns float."""
        rain = OpenWeatherMapRain(**{"1h": 3.5})
        serialized = rain.model_dump()
        assert serialized == 3.5


class TestOpenWeatherMapSnow:
    """Tests for OpenWeatherMapSnow class."""

    def test_snow_inherits_from_rain(self):
        """Test snow inherits from rain."""
        assert issubclass(OpenWeatherMapSnow, OpenWeatherMapRain)

    def test_snow_default_value(self):
        """Test snow with default value."""
        snow = OpenWeatherMapSnow()
        assert snow.one_hour == 0.0

    def test_snow_with_value(self):
        """Test snow with value."""
        snow = OpenWeatherMapSnow(**{"1h": 1.5})
        assert snow.one_hour == 1.5


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

        assert base.temp == 25.5
        assert base.feels_like == 26.0
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

    def test_base_data_with_rain(self):
        """Test base data with rain."""
        data = make_base_data()
        data["rain"] = {"1h": 2.5}
        base = OpenWeatherMapBaseData(**data)

        assert base.rain.one_hour == 2.5

    def test_base_data_with_snow(self):
        """Test base data with snow."""
        data = make_base_data()
        data["snow"] = {"1h": 1.0}
        base = OpenWeatherMapBaseData(**data)

        assert base.snow.one_hour == 1.0


class TestOpenWeatherMapCurrentData:
    """Tests for OpenWeatherMapCurrentData class."""

    def test_current_data_creation(self):
        """Test current data creation."""
        data = make_base_data()
        data["sunrise"] = datetime(2024, 6, 15, 5, 30, 0, tzinfo=timezone.utc)
        data["sunset"] = datetime(2024, 6, 15, 21, 30, 0, tzinfo=timezone.utc)

        current = OpenWeatherMapCurrentData(**data)

        assert current.temp == 25.5
        assert current.sunrise.hour == 5
        assert current.sunset.hour == 21


class TestOpenWeatherMapForecastData:
    """Tests for OpenWeatherMapForecastData class."""

    def test_forecast_data_creation(self):
        """Test forecast data creation."""
        data = make_base_data()
        data["pop"] = 0.25

        forecast = OpenWeatherMapForecastData(**data)

        assert forecast.temp == 25.5
        assert forecast.pop == 0.25


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

        assert base.lat == 52.52
        assert base.lon == 13.405
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

        assert one_call.lat == 52.52
        assert one_call.current.temp == 25.5
        assert len(one_call.hourly) == 1
        assert one_call.hourly[0].pop == 0.1
