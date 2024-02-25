from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field, computed_field, field_serializer, model_serializer

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
    wind_gust: Optional[float] = Field(None)
    weather: list[OpenWeatherMapCondition]
    rain: OpenWeatherMapRain = Field(OpenWeatherMapRain())
    irradiance: Optional[OpenWeatherMapIrradianceUnit] = Field(None)

    @property
    def localtime(self) -> datetime:
        return self.dt.astimezone()

    @computed_field
    @property
    def year(self) -> int:
        return self.localtime.year

    @computed_field
    @property
    def month(self) -> int:
        return self.localtime.month

    @computed_field
    @property
    def day(self) -> int:
        return self.localtime.day

    @computed_field
    @property
    def hour(self) -> int:
        return self.localtime.hour

    @field_serializer("dt")
    def serialize_dt(self, dt: datetime, _info):
        return dt.astimezone().isoformat()

    @field_serializer("weather")
    def serialize_weather(
        self, weather: list[OpenWeatherMapCondition], _info
    ) -> OpenWeatherMapCondition:
        return weather[0]


class OpenWeatherMapCurrentData(OpenWeatherMapBaseData):
    sunrise: datetime = Field(exclude=True)
    sunset: datetime = Field(exclude=True)


class OpenWeatherMapForecastData(OpenWeatherMapBaseData):
    pop: float

    def model_dump_estimation_data(self):
        model_dict = self.model_dump(exclude=["weather", "dt"], exclude_none=True)
        model_dict["weather_id"] = self.weather[0].id
        model_dict["weather_main"] = self.weather[0].main
        if "irradiance" in model_dict:
            irradiance = model_dict.pop("irradiance")
            for prefix in ["clear_sky", "cloudy_sky"]:
                model_dict[f"{prefix}_dhi"] = irradiance[prefix]["dhi"]
                model_dict[f"{prefix}_dni"] = irradiance[prefix]["dni"]
                model_dict[f"{prefix}_ghi"] = irradiance[prefix]["ghi"]
        return model_dict


class OpenWeatherMapOneCall(Solaredge2MQTTBaseModel):
    lat: float
    lon: float
    timezone: str
    timezone_offset: int
    current: OpenWeatherMapCurrentData
    hourly: list[OpenWeatherMapForecastData]


class OpenWeatherMapIrradiance(Solaredge2MQTTBaseModel):
    dni: float
    ghi: float
    dhi: float


class OpenWeatherMapIrradianceUnit(Solaredge2MQTTBaseModel):
    clear_sky: OpenWeatherMapIrradiance
    cloudy_sky: OpenWeatherMapIrradiance


class OpenWeatherMapIrradianceHour(OpenWeatherMapIrradianceUnit):
    hour: int = Field(exclude=True)


class OpenWeatherMapWeatherIrradianceData(Solaredge2MQTTBaseModel):
    daily: list[OpenWeatherMapIrradianceUnit] = Field(exclude=True)
    hourly: list[OpenWeatherMapIrradianceHour]


class OpenWeatherMapSolarData(Solaredge2MQTTBaseModel):
    lat: float
    lon: float
    date: str
    tz: str
    sunrise: datetime
    sunset: datetime
    irradiance: OpenWeatherMapWeatherIrradianceData
