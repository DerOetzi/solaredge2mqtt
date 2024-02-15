from datetime import datetime, timedelta, timezone

from influxdb_client import Point

from solaredge2mqtt.models.base import EnumModel, Solaredge2MQTTBaseModel


class ForecastAccount(EnumModel):
    PUBLIC = "Public", 1, 600, 60
    PERSONAL = "Personal", 1, 600, 30
    PERSONAL_PLUS = "Personal Plus", 2, 300, 15
    PROFESSSIONAL = "Professional", 3, 300, 15
    PROFESSSIONAL_PLUS = "Professional Plus", 4, 300, 15

    def __init__(
        self,
        account_name: str,
        allowed_strings: int,
        interval_in_seconds: int,
        resolution_in_minutes: int,
    ) -> None:
        self._account_name = account_name
        self._allowed_strings = allowed_strings
        self._interval_in_seconds = interval_in_seconds
        self._resolution_in_minutes = resolution_in_minutes

    @property
    def account_name(self) -> str:
        return self.account_name

    @property
    def allowed_strings(self) -> int:
        return self._allowed_strings

    @property
    def interval_in_seconds(self) -> int:
        return self._interval_in_seconds

    @property
    def resolution_in_minutes(self) -> int:
        return self._resolution_in_minutes


class ForecastAPIKeyInfo(Solaredge2MQTTBaseModel):
    account: ForecastAccount = ForecastAccount.PUBLIC

    model_config = {"extra": "ignore"}


class Forecast(Solaredge2MQTTBaseModel):
    watts: dict[datetime, int]
    watt_hours_period: dict[datetime, int]
    watt_hours: dict[datetime, int]
    watt_hours_day: dict[str, int]

    @property
    def influxdb_points(self) -> list[Point]:
        merged_power_and_energy = {
            k: (self.watts.get(k, 0), self.watt_hours_period.get(k, 0))
            for k in set(self.watts) | set(self.watt_hours_period)
        }

        points = [
            Point("forecast")
            .field("power", power)
            .field("energy", energy / 1000)
            .time(timestamp.astimezone(timezone.utc), write_precision="s")
            for timestamp, (power, energy) in merged_power_and_energy.items()
            if timestamp > datetime.now()
        ]

        return points


class ForecastQuery(EnumModel):
    ACTUAL = "actual_unit"
    NEXT = "forecast_unit"

    def __init__(self, query: str) -> None:
        self._query: str = query

    @property
    def query(self) -> str:
        return self._query


class ForecastPeriod(EnumModel):
    TODAY = "today", "1d", ForecastQuery.ACTUAL
    TOMORROW = "tomorrow", "1d", ForecastQuery.NEXT
    CURRENT_HOUR = "current_hour", "1h", ForecastQuery.ACTUAL
    NEXT_HOUR = "next_hour", "1h", ForecastQuery.NEXT

    def __init__(self, topic: str, unit: str, query: ForecastQuery) -> None:
        self._topic: str = topic
        self._unit: str = unit
        self._query: ForecastQuery = query

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def query(self) -> ForecastQuery:
        return self._query


class EnergyForecast(Solaredge2MQTTBaseModel):
    today: float
    tomorrow: float
    current_hour: float
    next_hour: float

    @classmethod
    def from_api(cls, forecast: Forecast):
        time_current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        time_next_hour = time_current_hour + timedelta(hours=1)

        current_hour = cls._calc_energy(forecast, time_current_hour, time_next_hour)

        time_next_two_hours = time_current_hour + timedelta(hours=2)

        next_hour = cls._calc_energy(forecast, time_next_hour, time_next_two_hours)

        time_current_day = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        time_next_day = time_current_day + timedelta(days=1)
        today = cls._calc_energy(forecast, time_current_day, time_next_day)

        time_next_two_days = time_current_day + timedelta(days=2)
        tomorrow = cls._calc_energy(forecast, time_next_day, time_next_two_days)

        return cls(
            today=today / 1000,
            tomorrow=tomorrow / 1000,
            current_hour=current_hour / 1000,
            next_hour=next_hour / 1000,
        )

    @staticmethod
    def _calc_energy(
        forecast: Forecast, start_time: datetime, end_time: datetime
    ) -> int:
        energy = 0
        for time, watt_hours in forecast.watt_hours_period.items():
            if time >= start_time and time < end_time:
                energy += watt_hours
            elif time >= end_time:
                break
        return energy
