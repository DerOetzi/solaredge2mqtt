from typing import ClassVar

from requests.exceptions import HTTPError

from solaredge2mqtt.eventbus import BaseEvent, EventBus
from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import OpenWeatherMapOneCall
from solaredge2mqtt.mqtt import MQTTPublishEvent
from solaredge2mqtt.service.http import HTTPClient
from solaredge2mqtt.settings import ServiceSettings

ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
TIMEMACHINE_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"


class WeatherUpdateEvent(BaseEvent):
    EVENT_TYPE: ClassVar[str] = "weather_update"
    weather: OpenWeatherMapOneCall

    @classmethod
    async def emit(cls, event_bus: EventBus, **kwargs) -> None:
        await event_bus.emit(cls(**kwargs))
        await MQTTPublishEvent.emit(
            event_bus, topic="weather/current", payload=kwargs["weather"].current
        )


class WeatherClient(HTTPClient):
    def __init__(self, settings: ServiceSettings, event_bus: EventBus) -> None:
        super().__init__("Weather API")

        self.location = settings.location
        self.settings = settings.weather

        self.event_bus = event_bus

    async def loop(self):
        weather = self.get_weather()
        await WeatherUpdateEvent.emit(self.event_bus, weather=weather)

    def get_weather(self) -> OpenWeatherMapOneCall:
        try:
            logger.info("Reading weather data from OpenWeatherMap")
            result = self._get(
                ONECALL_URL,
                params={
                    "lat": self.location.latitude,
                    "lon": self.location.longitude,
                    "exclude": "minutely,daily,alerts",
                    "units": "metric",
                    "lang": self.settings.language,
                    "appid": self.settings.api_key.get_secret_value(),
                },
                timeout=7,
            )

            logger.trace(result)

            if result is None:
                raise InvalidDataException(
                    "Unable to read weather data from OpenWeatherMap"
                )

            weather = OpenWeatherMapOneCall(**result)

            return weather
        except HTTPError as error:
            status_code = error.response.status_code
            if status_code == 401:
                error_msg = (
                    "Invalid OpenWeatherMap API key or no subscription to OneCall-API"
                )
            else:
                error_msg = "Unable to read weather data from OpenWeatherMap (HTTP {status_code})"

            raise InvalidDataException(error_msg) from error
