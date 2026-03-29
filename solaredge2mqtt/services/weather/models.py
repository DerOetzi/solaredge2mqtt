from __future__ import annotations

from datetime import datetime
from typing import TypeAlias

from pydantic import Field, field_serializer, model_serializer

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel

WeatherData: TypeAlias = dict[
    str,
    str | float | int | datetime | None,
]


class OpenWeatherMapOneCallBase(Solaredge2MQTTBaseModel):
    lat: float
    lon: float
    timezone: str
    timezone_offset: int


class OpenWeatherMapOneCall(OpenWeatherMapOneCallBase):
    current: OpenWeatherMapCurrentData
    hourly: list[OpenWeatherMapForecastData]


class OpenWeatherMapRain(Solaredge2MQTTBaseModel):
    one_hour: float = Field(default=0.0, alias="1h")

    @model_serializer
    def ser_model(self) -> float:
        return self.one_hour


class OpenWeatherMapSnow(OpenWeatherMapRain): ...  # pragma: no cover


class OpenWeatherMapBaseData(Solaredge2MQTTBaseModel):
    dt: datetime
    temp: float | None = Field(default=None)
    feels_like: float | None = Field(default=None)
    pressure: int | None = Field(default=None)
    humidity: int | None = Field(default=None)
    dew_point: float | None = Field(default=None)
    uvi: float | None = Field(default=None)
    clouds: int | None = Field(default=None)
    visibility: int | None = Field(default=None)
    wind_speed: float | None = Field(default=None)
    wind_deg: int | None = Field(default=None)
    wind_gust: float | None = Field(default=None)
    weather: list[OpenWeatherMapCondition]
    rain: OpenWeatherMapRain = Field(default_factory=OpenWeatherMapRain)
    snow: OpenWeatherMapSnow = Field(default_factory=OpenWeatherMapSnow)

    @property
    def localtime(self) -> datetime:
        return self.dt.astimezone()

    @property
    def year(self) -> int:
        return self.localtime.year

    @property
    def month(self) -> int:
        return self.localtime.month

    @property
    def day(self) -> int:
        return self.localtime.day

    @property
    def hour(self) -> int:
        return self.localtime.hour

    @field_serializer("dt")
    def serialize_dt(self, dt: datetime, _info) -> str:
        return dt.astimezone().isoformat()

    @field_serializer("weather")
    def serialize_weather(
        self, weather: list[OpenWeatherMapCondition], _info
    ) -> OpenWeatherMapCondition:
        return weather[0]

    def model_dump_estimation_data(self) -> WeatherData:
        model_dict = self.model_dump(exclude={"weather", "dt"}, exclude_none=True)
        model_dict["weather_id"] = self.weather[0].id
        model_dict["weather_main"] = self.weather[0].main
        return model_dict


class OpenWeatherMapCurrentData(OpenWeatherMapBaseData):
    sunrise: datetime = Field(exclude=True)
    sunset: datetime = Field(exclude=True)


class OpenWeatherMapForecastData(OpenWeatherMapBaseData):
    pop: float


class OpenWeatherMapCondition(Solaredge2MQTTBaseModel):
    id: int
    main: str
    description: str
    icon: str = Field(exclude=True)
