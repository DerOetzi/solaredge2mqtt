from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer, model_serializer

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel


class OpenWeatherMapOneCallBase(Solaredge2MQTTBaseModel):
    lat: float
    lon: float
    timezone: str
    timezone_offset: int


class OpenWeatherMapOneCall(OpenWeatherMapOneCallBase):
    current: OpenWeatherMapCurrentData
    hourly: list[OpenWeatherMapForecastData]


class OpenWeatherMapRain(Solaredge2MQTTBaseModel):
    one_hour: float = Field(0.0, alias="1h")

    @model_serializer
    def ser_model(self) -> float:
        return self.one_hour


class OpenWeatherMapSnow(OpenWeatherMapRain):
    pass


class OpenWeatherMapBaseData(Solaredge2MQTTBaseModel):
    dt: datetime
    temp: float | None = Field(None)
    feels_like: float | None = Field(None)
    pressure: int | None = Field(None)
    humidity: int | None = Field(None)
    dew_point: float | None = Field(None)
    uvi: float | None = Field(None)
    clouds: int | None = Field(None)
    visibility: int | None = Field(None)
    wind_speed: float | None = Field(None)
    wind_deg: int | None = Field(None)
    wind_gust: float | None = Field(None)
    weather: list[OpenWeatherMapCondition]
    rain: OpenWeatherMapRain = Field(OpenWeatherMapRain())
    snow: OpenWeatherMapSnow = Field(OpenWeatherMapSnow())

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


class OpenWeatherMapForecastData(OpenWeatherMapBaseData):
    pop: float


class OpenWeatherMapCondition(Solaredge2MQTTBaseModel):
    id: int
    main: str
    description: str
    icon: str = Field(exclude=True)
