from datetime import datetime, timedelta

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
            .time(timestamp, write_precision="s")
            for timestamp, (power, energy) in merged_power_and_energy.items()
        ]

        return points


class EnergyForecast(Solaredge2MQTTBaseModel):
    current_day: int
    next_day: int
    current_hour: int
    next_hour: int
    next_three_hours: int

    def __init__(self, forecast: Forecast):
        time_current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        time_next_hour = time_current_hour + timedelta(hours=1)

        current_hour = self._calc_energy(forecast, time_current_hour, time_next_hour)

        time_next_two_hours = time_current_hour + timedelta(hours=2)

        next_hour = self._calc_energy(forecast, time_next_hour, time_next_two_hours)

        time_next_three_hours = time_current_hour + timedelta(hours=3)

        next_three_hours = self._calc_energy(
            forecast, time_current_hour, time_next_three_hours
        )

        time_current_day = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        time_next_day = time_current_day + timedelta(days=1)
        current_day = self._calc_energy(forecast, time_current_day, time_next_day)

        time_next_two_days = time_current_day + timedelta(days=2)
        next_day = self._calc_energy(forecast, time_next_day, time_next_two_days)

        super().__init__(
            current_day=current_day,
            next_day=next_day,
            current_hour=current_hour,
            next_hour=next_hour,
            next_three_hours=next_three_hours,
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
