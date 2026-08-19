from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_serializer

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel

WeatherData = dict[str, str | float | int | datetime | None]


class WeatherSnapshot(Solaredge2MQTTBaseModel):
    """One interval of weather in pvlearn's canonical schema.

    Every provider adapter translates its own payload onto these names, so
    nothing behind the weather service knows which provider a snapshot came
    from beyond the `weather_provider` field it carries. The fields mirror
    `pvlearn.schema`; a provider that does not deliver one leaves it unset.
    """

    time: datetime
    weather_provider: str

    cloud_cover: float | None = Field(default=None)
    temperature: float | None = Field(default=None)
    apparent_temperature: float | None = Field(default=None)
    dew_point: float | None = Field(default=None)
    relative_humidity: float | None = Field(default=None)
    surface_pressure: float | None = Field(default=None)
    precipitation: float | None = Field(default=None)
    precipitation_probability: float | None = Field(default=None)
    uv_index: float | None = Field(default=None)
    visibility: float | None = Field(default=None)
    wind_speed: float | None = Field(default=None)
    wind_gust: float | None = Field(default=None)
    ghi: float | None = Field(default=None)
    dni: float | None = Field(default=None)
    dhi: float | None = Field(default=None)

    condition_code: int | None = Field(default=None)

    wind_direction: float | None = Field(default=None)

    @field_serializer("time")
    def serialize_time(self, time: datetime, _info) -> str:
        return time.astimezone().isoformat()

    @property
    def localtime(self) -> datetime:
        return self.time.astimezone()

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

    def model_dump_canonical(self) -> WeatherData:
        """The snapshot as pvlearn consumes it, without the unset features."""
        return self.model_dump(exclude={"timestamp", "time"}, exclude_none=True)


class WeatherResult(Solaredge2MQTTBaseModel):
    """What a weather provider delivers, translated onto the canonical schema."""

    weather_provider: str
    current: WeatherSnapshot
    hourly: list[WeatherSnapshot]
