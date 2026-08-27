from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.status.events import ServiceOfflineEvent, ServiceOnlineEvent
from solaredge2mqtt.services.weather.result import WeatherResult


class WeatherUpdateEvent(BaseEvent):
    def __init__(self, weather: WeatherResult) -> None:
        self._weather = weather

    @property
    def weather(self) -> WeatherResult:
        return self._weather


class WeatherOnlineEvent(ServiceOnlineEvent):
    SERVICE_NAME = "weather_api"


class WeatherOfflineEvent(ServiceOfflineEvent):
    SERVICE_NAME = "weather_api"
