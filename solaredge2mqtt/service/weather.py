from datetime import datetime

from requests.exceptions import HTTPError

from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import OpenWeatherMapOneCall, OpenWeatherMapSolarData
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.service.http import HTTPClient
from solaredge2mqtt.settings import ServiceSettings

ONECALL_URL = "https://api.openweathermap.org/data/3.0/onecall"
SOLAR_URL = "https://api.openweathermap.org/energy/1.0/solar/data"


class WeatherClient(HTTPClient):
    def __init__(self, settings: ServiceSettings, mqtt: MQTTClient) -> None:
        super().__init__("Weather API")

        self.location = settings.location
        self.settings = settings.weather

        self.mqtt = mqtt

    async def loop(self):
        weather = self.get_weather()
        await self.mqtt.publish_to("weather/current", weather.current)

    def get_weather(self, with_irradiance: bool = False) -> OpenWeatherMapOneCall:
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
            )

            logger.trace(result)
            weather = OpenWeatherMapOneCall(**result)

            if with_irradiance:
                weather = self._merge_irradiance(weather)

            return weather
        except HTTPError as error:
            raise InvalidDataException("Unable to read weather data") from error

    def _merge_irradiance(
        self, weather: OpenWeatherMapOneCall
    ) -> OpenWeatherMapOneCall:
        irradiance = None

        for hour_forecast in weather.hourly:
            date = f"{hour_forecast.year}-{hour_forecast.month}-{hour_forecast.day}"
            if irradiance is None or irradiance.date != date:
                logger.info("Retrieving irradiance for {date}", date=date)
                irradiance = self.get_irradiance(date)

            hour_forecast.irradiance = irradiance.irradiance.hourly[hour_forecast.hour]

        return weather

    def get_irradiance(self, date: str) -> OpenWeatherMapSolarData:
        try:
            result = self._get(
                SOLAR_URL,
                params={
                    "lat": self.location.latitude,
                    "lon": self.location.longitude,
                    "date": date,
                    "appid": self.settings.api_key.get_secret_value(),
                },
            )

            logger.trace(result)
            return OpenWeatherMapSolarData(**result)
        except HTTPError as error:
            raise InvalidDataException("Unable to read weather data") from error
