"""Tests for weather events module."""

from datetime import datetime, timezone

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.models import OpenWeatherMapOneCall


class TestWeatherUpdateEvent:
    """Tests for WeatherUpdateEvent class."""

    def test_event_is_base_event(self):
        """Test WeatherUpdateEvent inherits from BaseEvent."""
        assert issubclass(WeatherUpdateEvent, BaseEvent)

    def test_event_weather_property(self):
        """Test weather property."""
        # Create a minimal weather object for testing with all required fields
        weather_data = {
            "lat": 52.52,
            "lon": 13.405,
            "timezone": "Europe/Berlin",
            "timezone_offset": 3600,
            "current": {
                "dt": 1609459200,
                "temp": 10.5,
                "humidity": 80,
                "clouds": 75,
                "sunrise": 1609488000,
                "sunset": 1609520400,
                "weather": [
                    {
                        "id": 804,
                        "main": "Clouds",
                        "description": "overcast clouds",
                        "icon": "04d",
                    }
                ],
            },
            "hourly": [],
        }

        weather = OpenWeatherMapOneCall(**weather_data)
        event = WeatherUpdateEvent(weather)

        assert event.weather is weather
        assert event.weather.lat == 52.52
        assert event.weather.lon == 13.405
