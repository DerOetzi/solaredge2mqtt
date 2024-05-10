from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.weather.models import OpenWeatherMapOneCall


class WeatherUpdateEvent(BaseEvent):
    def __init__(self, weather: OpenWeatherMapOneCall) -> None:
        self._weather = weather

    @property
    def weather(self) -> OpenWeatherMapOneCall:
        return self._weather
