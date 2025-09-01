from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiohttp import ClientResponseError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent
from solaredge2mqtt.services.http_async import HTTPClientAsync
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.models import OpenWeatherMapOneCall

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings import ServiceSettings

ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
TIMEMACHINE_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"


class WeatherClient(HTTPClientAsync):
    def __init__(self, settings: ServiceSettings, event_bus: EventBus) -> None:
        super().__init__("Weather API")

        self.location = settings.location
        self.settings = settings.weather

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self):
        self.event_bus.subscribe(Interval10MinTriggerEvent, self.loop)

    async def loop(self, _):
        weather = await self.get_weather()
        await self.event_bus.emit(WeatherUpdateEvent(weather))
        await self.event_bus.emit(
            MQTTPublishEvent(
                "weather/current",
                weather.current,
                self.settings.retain,
            )
        )

    async def get_weather(self) -> OpenWeatherMapOneCall:
        try:
            logger.info("Reading weather data from OpenWeatherMap")
            async with asyncio.timeout(7):
                result = await self._get(
                    ONECALL_URL,
                    params={
                        "lat": self.location.latitude,
                        "lon": self.location.longitude,
                        "exclude": "minutely,daily,alerts",
                        "units": "metric",
                        "lang": self.settings.language,
                        "appid": self.settings.api_key.get_secret_value(),
                    },
                )
            logger.trace(result)

            if result is None:
                raise InvalidDataException(
                    "Unable to read weather data from OpenWeatherMap"
                )

            weather = OpenWeatherMapOneCall(**result)

            return weather
        except ClientResponseError as error:
            status_code = error.status
            if status_code == 401:
                error_msg = (
                    "Invalid OpenWeatherMap API key or no subscription to OneCall-API"
                )
            else:
                error_msg = (
                    "Unable to read weather data from OpenWeatherMap "
                    "(HTTP {status_code})"
                )

            raise InvalidDataException(error_msg) from error
        except asyncio.TimeoutError as error:
            raise InvalidDataException(
                "Unable to read weather data from OpenWeatherMap (timeout)"
            ) from error
