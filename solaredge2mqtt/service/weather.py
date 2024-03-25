from requests.exceptions import HTTPError

from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import OpenWeatherMapOneCall
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.service.http import HTTPClient
from solaredge2mqtt.settings import ServiceSettings

ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
TIMEMACHINE_URL = "https://api.openweathermap.org/data/3.0/onecall/timemachine"


class WeatherClient(HTTPClient):
    def __init__(self, settings: ServiceSettings, mqtt: MQTTClient) -> None:
        super().__init__("Weather API")

        self.location = settings.location
        self.settings = settings.weather

        self.mqtt = mqtt

    async def loop(self):
        weather = self.get_weather()
        await self.mqtt.publish_to("weather/current", weather.current)

    def get_weather(self) -> OpenWeatherMapOneCall:
        try:
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
                raise InvalidDataException("Unable to read weather data")

            weather = OpenWeatherMapOneCall(**result)

            return weather
        except HTTPError as error:
            raise InvalidDataException("Unable to read weather data") from error
