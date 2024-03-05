from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer, model_serializer

from solaredge2mqtt.models.base import Solaredge2MQTTBaseModel


class OpenWeatherMapCondition(Solaredge2MQTTBaseModel):
    id: int
    main: str
    description: str
    icon: str = Field(exclude=True)


class OpenWeatherMapRain(Solaredge2MQTTBaseModel):
    one_hour: float = Field(0.0, alias="1h")

    @model_serializer
    def ser_model(self) -> float:
        return self.one_hour


class OpenWeatherMapBaseData(Solaredge2MQTTBaseModel):
    dt: datetime
    temp: float
    feels_like: float
    pressure: int
    humidity: int
    dew_point: float
    uvi: float
    clouds: int
    visibility: int
    wind_speed: float
    wind_deg: int
    wind_gust: float | None = Field(None)
    weather: list[OpenWeatherMapCondition]
    rain: OpenWeatherMapRain = Field(OpenWeatherMapRain())

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

    def model_dump_estimation_data(self) -> dict[str, str | float | int | None]:
        model_dict = self.model_dump(exclude=["weather", "dt"], exclude_none=True)
        model_dict["weather_id"] = self.weather[0].id
        model_dict["weather_main"] = self.weather[0].main
        return model_dict


class OpenWeatherMapCurrentData(OpenWeatherMapBaseData):
    sunrise: datetime = Field(exclude=True)
    sunset: datetime = Field(exclude=True)
    pop: float = Field(0.0)


class OpenWeatherMapForecastData(OpenWeatherMapBaseData):
    pop: float


class OpenWeatherMapOneCall(Solaredge2MQTTBaseModel):
    lat: float
    lon: float
    timezone: str
    timezone_offset: int
    current: OpenWeatherMapCurrentData
    hourly: list[OpenWeatherMapForecastData]
