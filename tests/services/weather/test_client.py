"""Tests for WeatherClient with mocking."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, RequestInfo

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.weather import WeatherClient
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()
    settings.location = MagicMock()
    settings.location.latitude = 52.52
    settings.location.longitude = 13.405

    settings.weather = MagicMock()
    settings.weather.api_key = MagicMock()
    settings.weather.api_key.get_secret_value.return_value = "test_api_key"
    settings.weather.language = "en"
    settings.weather.retain = False

    return settings


@pytest.fixture
def mock_weather_response():
    """Create mock weather API response."""
    return {
        "lat": 52.52,
        "lon": 13.405,
        "timezone": "Europe/Berlin",
        "timezone_offset": 3600,
        "current": {
            "dt": 1609459200,
            "sunrise": 1609488000,
            "sunset": 1609520400,
            "temp": 5.5,
            "feels_like": 2.3,
            "pressure": 1013,
            "humidity": 80,
            "dew_point": 2.5,
            "uvi": 0.5,
            "clouds": 75,
            "visibility": 10000,
            "wind_speed": 5.5,
            "wind_deg": 220,
            "weather": [
                {
                    "id": 803,
                    "main": "Clouds",
                    "description": "broken clouds",
                    "icon": "04d",
                }
            ],
        },
        "hourly": [],
    }


class TestWeatherClientInit:
    """Tests for WeatherClient initialization."""

    def test_weather_client_init(self, mock_service_settings, mock_event_bus):
        """Test WeatherClient initialization."""
        client = WeatherClient(mock_service_settings, mock_event_bus)

        assert client.location is mock_service_settings.location
        assert client.settings is mock_service_settings.weather
        assert client.event_bus is mock_event_bus

    def test_weather_client_subscribes_to_events(
        self, mock_service_settings, mock_event_bus
    ):
        """Test WeatherClient subscribes to 10min interval event."""
        client = WeatherClient(mock_service_settings, mock_event_bus)

        mock_event_bus.subscribe.assert_called()


class TestWeatherClientGetWeather:
    """Tests for WeatherClient get_weather."""

    @pytest.mark.asyncio
    async def test_get_weather_success(
        self, mock_service_settings, mock_event_bus, mock_weather_response
    ):
        """Test successful weather retrieval."""
        client = WeatherClient(mock_service_settings, mock_event_bus)
        client._get = AsyncMock(return_value=mock_weather_response)

        result = await client.get_weather()

        assert result.lat == 52.52
        assert result.lon == 13.405
        assert result.current is not None

    @pytest.mark.asyncio
    async def test_get_weather_none_response(
        self, mock_service_settings, mock_event_bus
    ):
        """Test get_weather raises when response is None."""
        client = WeatherClient(mock_service_settings, mock_event_bus)
        client._get = AsyncMock(return_value=None)

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_weather()

        assert "Unable to read weather data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_weather_401_error(
        self, mock_service_settings, mock_event_bus
    ):
        """Test get_weather handles 401 error."""
        client = WeatherClient(mock_service_settings, mock_event_bus)

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "http://test.com"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=401,
        )
        client._get = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_weather()

        assert "Invalid OpenWeatherMap API key" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_weather_other_http_error(
        self, mock_service_settings, mock_event_bus
    ):
        """Test get_weather handles other HTTP errors."""
        client = WeatherClient(mock_service_settings, mock_event_bus)

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "http://test.com"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=500,
        )
        client._get = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_weather()

        assert "Unable to read weather data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_weather_timeout(
        self, mock_service_settings, mock_event_bus
    ):
        """Test get_weather handles timeout."""
        client = WeatherClient(mock_service_settings, mock_event_bus)
        client._get = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_weather()

        assert "timeout" in exc_info.value.message


class TestWeatherClientLoop:
    """Tests for WeatherClient loop."""

    @pytest.mark.asyncio
    async def test_loop_success(
        self, mock_service_settings, mock_event_bus, mock_weather_response
    ):
        """Test loop publishes weather data."""
        client = WeatherClient(mock_service_settings, mock_event_bus)
        client._get = AsyncMock(return_value=mock_weather_response)

        await client.loop(None)

        # Should emit WeatherUpdateEvent and MQTTPublishEvent
        assert mock_event_bus.emit.call_count == 2

        # Check first call is WeatherUpdateEvent
        first_call = mock_event_bus.emit.call_args_list[0]
        assert isinstance(first_call[0][0], WeatherUpdateEvent)

        # Check second call is MQTTPublishEvent
        second_call = mock_event_bus.emit.call_args_list[1]
        assert isinstance(second_call[0][0], MQTTPublishEvent)
        assert second_call[0][0].topic == "weather/current"
