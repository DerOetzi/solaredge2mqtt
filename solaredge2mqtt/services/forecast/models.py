from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
from typing import Any

from pvlearn.result import ForecastResult
from pydantic import PrivateAttr, computed_field, model_validator
from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType as HABinarySensor,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import Component

__all__ = ["Forecast", "ForecastChargeWindow", "ForecastPeriod"]

#: The interval the published forecast covers per period.
INTERVAL_MINUTES = 60


@dataclass(frozen=True)
class ForecastPeriod:
    time: datetime
    value: int


@dataclass(frozen=True)
class ForecastChargeWindow:
    periods: list[ForecastPeriod]
    target_covered: bool

    @property
    def start_time(self) -> datetime:
        return self.periods[0].time

    @property
    def period_count(self) -> int:
        return len(self.periods)


class Forecast(Component, ForecastResult):
    COMPONENT = "forecast"

    #: Deprecated, removed after at least two minor releases. Derived from
    #: `energy_period`, with which it is numerically identical at 60 minutes.
    #: See `docs/decisions/0002-canonical-weather-schema.md`.
    power_period: SkipJsonSchema[dict[datetime, int]]
    energy_period: SkipJsonSchema[dict[datetime, int]]
    production_threshold_wh: SkipJsonSchema[float]
    battery_charge_needed_wh: SkipJsonSchema[float | None] = None
    battery_charge_slot_cap_wh: SkipJsonSchema[float | None] = None

    _periods_today: list[ForecastPeriod] = PrivateAttr(default_factory=list)
    _production_hours: list[ForecastPeriod] = PrivateAttr(default_factory=list)
    _peak_period: ForecastPeriod | None = PrivateAttr(default=None)
    _charge_window: ForecastChargeWindow | None = PrivateAttr(default=None)

    @classmethod
    def from_energy_period(
        cls,
        energy_period: dict[datetime, int],
        timezone: str,
        production_threshold_wh: float,
        battery_charge_needed_wh: float | None = None,
        battery_charge_slot_cap_wh: float | None = None,
    ) -> Forecast:
        return cls(
            interval_minutes=INTERVAL_MINUTES,
            timezone=timezone,
            energy_period=energy_period,
            power_period=dict(energy_period),
            production_threshold_wh=production_threshold_wh,
            battery_charge_needed_wh=battery_charge_needed_wh,
            battery_charge_slot_cap_wh=battery_charge_slot_cap_wh,
        )

    @model_validator(mode="after")
    def _derive_today(self) -> Forecast:
        self._periods_today = self._collect_periods_today()
        self._production_hours = self._collect_production_hours()
        self._peak_period = self._find_peak_period()
        self._charge_window = self._build_charge_window()

        return self

    def _collect_periods_today(self) -> list[ForecastPeriod]:
        today = self._now_local().date()
        return sorted(
            (
                ForecastPeriod(period.instant, energy)
                for period, energy in self._periods()
                if period.local.date() == today
            ),
            key=lambda period: period.time,
        )

    def _collect_production_hours(self) -> list[ForecastPeriod]:
        return [
            period
            for period in self._periods_today
            if period.value > self.production_threshold_wh
        ]

    def _find_peak_period(self) -> ForecastPeriod | None:
        if not self._production_hours:
            return None

        return max(self._production_hours, key=lambda period: period.value)

    def _build_charge_window(self) -> ForecastChargeWindow | None:
        if not self.battery_charge_needed_wh or self.battery_charge_needed_wh <= 0:
            return None

        if self._peak_period is None:
            return None

        periods = self._production_hours
        anchor = periods.index(self._peak_period)
        first, last = anchor, anchor
        charged = self._charged(periods[anchor])

        while charged < self.battery_charge_needed_wh:
            before = periods[first - 1] if first > 0 else None
            after = periods[last + 1] if last + 1 < len(periods) else None

            if before is not None and self._is_wall(before, periods[first]):
                before = None
            if after is not None and self._is_wall(periods[last], after):
                after = None

            if before is None and after is None:
                return ForecastChargeWindow(
                    periods[first : last + 1], target_covered=False
                )

            if before is None:
                take_before = False
            elif after is None:
                take_before = True
            elif before.value <= after.value:
                take_before = False
            else:
                take_before = (
                    charged + self._charged(before) <= self.battery_charge_needed_wh
                )

            if take_before:
                first -= 1
                charged += self._charged(periods[first])
            else:
                last += 1
                charged += self._charged(periods[last])

        return ForecastChargeWindow(periods[first : last + 1], target_covered=True)

    def _charged(self, period: ForecastPeriod) -> float:
        if self.battery_charge_slot_cap_wh is None:
            return float(period.value)

        return min(float(period.value), self.battery_charge_slot_cap_wh)

    def _is_wall(self, left: ForecastPeriod, right: ForecastPeriod) -> bool:
        gap = right.time - left.time
        return gap.total_seconds() > self.interval_minutes * 60

    def _current_hour_start(self) -> datetime:
        return self._instant(self._hour_start(self._now_local()))

    @computed_field(**HASensor.ENERGY_WH.field("Energy production today"))
    @property
    def energy_today(self) -> int:
        return super().energy_today

    @computed_field(**HASensor.ENERGY_WH.field("Energy production remaining today"))
    @property
    def energy_today_remaining(self) -> int:
        return super().energy_today_remaining

    @computed_field(**HASensor.ENERGY_WH.field("Energy production current hour"))
    @property
    def energy_current_hour(self) -> int:
        return super().energy_current_hour

    @computed_field(**HASensor.ENERGY_WH.field("Energy production next hour"))
    @property
    def energy_next_hour(self) -> int:
        return super().energy_next_hour

    @computed_field(**HASensor.ENERGY_WH.field("Energy production tomorrow"))
    @property
    def energy_tomorrow(self) -> int:
        return super().energy_tomorrow

    @computed_field(**HASensor.TIMESTAMP.field("Energy production peak time today"))
    @property
    def energy_peak_time_today(self) -> datetime | None:
        return self._peak_period.time if self._peak_period else None

    @computed_field(**HASensor.ENERGY_WH.field("Energy production peak today"))
    @property
    def energy_peak_today(self) -> int:
        return self._peak_period.value if self._peak_period else 0

    @computed_field(**HASensor.ENERGY_WH.field("Energy production average today"))
    @property
    def energy_average_today(self) -> int:
        production = [period.value for period in self._production_hours]
        return int(round(mean(production))) if production else 0

    @computed_field(**HASensor.ENERGY_WH.field("Energy production median today"))
    @property
    def energy_median_today(self) -> int:
        production = [period.value for period in self._production_hours]
        return int(round(median(production))) if production else 0

    @computed_field(**HASensor.TIMESTAMP.field("Battery charge optimal start time"))
    @property
    def battery_charge_optimal_start_time(self) -> datetime | None:
        if self._charge_window is None:
            return None

        if not self._charge_window.target_covered:
            return self._current_hour_start()

        return self._charge_window.start_time

    @computed_field(**HASensor.DURATION_H.field("Battery charge duration"))
    @property
    def battery_charge_duration(self) -> float | None:
        if self._charge_window is None:
            return None

        return round(self._charge_window.period_count * self.interval_minutes / 60, 2)

    @computed_field(
        **HABinarySensor.STATUS.field("Battery charge target covered today")
    )
    @property
    def battery_charge_target_covered_today(self) -> bool | None:
        if self._charge_window is None:
            return None

        return self._charge_window.target_covered

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self._default_homeassistant_device_info("Forecast")
