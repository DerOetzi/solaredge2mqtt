from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, TypeAlias, cast

from pydantic import Field, field_serializer, model_serializer

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel

if TYPE_CHECKING:
    from pandas import DataFrame

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
    """One weather snapshot, both under OpenWeatherMap's names and canonically.

    Snapshots are persisted under the provider's own field names, so the
    translation to pvlearn's canonical schema happens on the way to the model.
    See `docs/decisions/0002-canonical-weather-schema.md`.
    """

    #: OpenWeatherMap One Call field -> canonical feature name. Fields with no
    #: canonical counterpart are absent, and so are the canonical irradiance
    #: features `ghi`, `dni` and `dhi`, which OpenWeatherMap does not deliver.
    CANONICAL_FIELDS: ClassVar[dict[str, str]] = {
        "clouds": "cloud_cover",
        "temp": "temperature",
        "feels_like": "apparent_temperature",
        "dew_point": "dew_point",
        "humidity": "relative_humidity",
        "pressure": "surface_pressure",
        "rain": "precipitation",
        "pop": "precipitation_probability",
        "uvi": "uv_index",
        "visibility": "visibility",
        "wind_speed": "wind_speed",
        "wind_gust": "wind_gust",
        "wind_deg": "wind_direction",
        "weather_id": "condition_code",
    }

    #: OpenWeatherMap condition id -> WMO 4677 weather code, the code space the
    #: canonical `condition_code` uses. Lossy in both directions; where WMO has
    #: no equivalent, the nearest optically similar condition is used. See
    #: `docs/decisions/0002-canonical-weather-schema.md`.
    CONDITION_TO_WMO: ClassVar[dict[int, int]] = {
        # Thunderstorm. WMO distinguishes hail (96, 99), OpenWeatherMap does not.
        200: 95,
        201: 95,
        202: 95,
        210: 95,
        211: 95,
        212: 95,
        221: 95,
        230: 95,
        231: 95,
        232: 95,
        # Drizzle.
        300: 51,
        301: 53,
        302: 55,
        310: 51,
        311: 53,
        312: 55,
        313: 81,
        314: 82,
        321: 80,
        # Rain.
        500: 61,
        501: 63,
        502: 65,
        503: 65,
        504: 65,
        511: 66,
        520: 80,
        521: 81,
        522: 82,
        531: 82,
        # Snow, including the mixed forms WMO files under showers.
        600: 71,
        601: 73,
        602: 75,
        611: 85,
        612: 85,
        613: 86,
        615: 71,
        616: 73,
        620: 85,
        621: 85,
        622: 86,
        # Atmosphere. Mist, smoke, haze, dust, sand and ash all scatter light
        # the way fog does, which is the only property that matters here.
        701: 45,
        711: 45,
        721: 45,
        731: 45,
        741: 45,
        751: 45,
        761: 45,
        762: 45,
        771: 80,
        781: 99,
        # Clear and clouds.
        800: 0,
        801: 1,
        802: 2,
        803: 3,
        804: 3,
    }

    #: What an unknown condition id becomes: overcast.
    UNKNOWN_CONDITION_WMO_CODE: ClassVar[int] = 3

    CONDITION_FIELD: ClassVar[str] = "weather_id"

    #: Canonical feature naming the provider a row came from. pvlearn treats it
    #: as a per-row categorical feature rather than a training-run setting, so
    #: the adapter stamps its own name onto every row it hands over.
    PROVIDER_FIELD: ClassVar[str] = "weather_provider"
    PROVIDER_NAME: ClassVar[str] = "openweathermap"

    #: Columns of a `forecast_training` frame the forecaster needs under their
    #: stored names, next to the translated weather fields.
    TRAINING_FIELDS: ClassVar[tuple[str, ...]] = ("time", "energy")

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
        """The snapshot under OpenWeatherMap's own field names, for persistence."""
        model_dict = self.model_dump(exclude={"weather", "dt"}, exclude_none=True)
        model_dict["weather_id"] = self.weather[0].id
        model_dict["weather_main"] = self.weather[0].main
        return model_dict

    def model_dump_canonical(self) -> WeatherData:
        """The snapshot in pvlearn's canonical schema, for the model.

        Fields without a canonical counterpart are dropped.
        """
        return self.to_canonical(self.model_dump_estimation_data())

    @classmethod
    def to_wmo_code(cls, condition_id: int | float | None) -> int | None:
        """Translate one OpenWeatherMap condition id to its WMO code."""
        if condition_id is None:
            return None

        return cls.CONDITION_TO_WMO.get(
            int(condition_id), cls.UNKNOWN_CONDITION_WMO_CODE
        )

    @classmethod
    def to_canonical(cls, estimation_data: Mapping[str, Any]) -> WeatherData:
        """Rename one weather snapshot onto the canonical schema."""
        canonical: WeatherData = {cls.PROVIDER_FIELD: cls.PROVIDER_NAME}

        for field, value in estimation_data.items():
            canonical_name = cls.CANONICAL_FIELDS.get(field)
            if canonical_name is None:
                continue

            if field == cls.CONDITION_FIELD:
                value = cls.to_wmo_code(
                    value if isinstance(value, (int, float)) else None
                )

            canonical[canonical_name] = value

        return canonical

    @classmethod
    def to_canonical_frame(cls, data: DataFrame) -> DataFrame:
        """Rename a `forecast_training` frame onto the canonical schema.

        Columns without a canonical counterpart are dropped, except the
        `TRAINING_FIELDS`, which the forecaster needs under those exact names.
        Rows older than a field's introduction simply carry NaN, which the
        forecaster tolerates. Every row is stamped with `PROVIDER_NAME`: the
        stored snapshots all come from this adapter.
        """
        canonical = data.copy()

        if cls.CONDITION_FIELD in canonical.columns:
            canonical[cls.CONDITION_FIELD] = canonical[cls.CONDITION_FIELD].map(
                cls.to_wmo_code
            )

        keep = {
            **cls.CANONICAL_FIELDS,
            **{field: field for field in cls.TRAINING_FIELDS},
        }
        canonical = cast(
            "DataFrame", canonical[[col for col in canonical.columns if col in keep]]
        )
        canonical.columns = [keep[str(col)] for col in canonical.columns]
        canonical[cls.PROVIDER_FIELD] = cls.PROVIDER_NAME

        return canonical


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
