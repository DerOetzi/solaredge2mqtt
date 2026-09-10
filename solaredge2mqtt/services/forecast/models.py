from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
from typing import Any

from pvlearn.result import ForecastResult
from pydantic import computed_field
from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType as HABinarySensor,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import Component

__all__ = ["Forecast", "Period"]

#: The interval the published forecast covers per period.
INTERVAL_MINUTES = 60


@dataclass(frozen=True)
class Period:
    time: datetime
    value: int


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
        peak = self._peak_period_today()
        return peak.time if peak else None

    @computed_field(**HASensor.ENERGY_WH.field("Energy production peak today"))
    @property
    def energy_peak_today(self) -> int:
        peak = self._peak_period_today()
        return peak.value if peak else 0

    @computed_field(**HASensor.ENERGY_WH.field("Energy production average today"))
    @property
    def energy_average_today(self) -> int:
        production = self._production_periods_today()
        return int(round(mean(production))) if production else 0

    @computed_field(**HASensor.ENERGY_WH.field("Energy production median today"))
    @property
    def energy_median_today(self) -> int:
        production = self._production_periods_today()
        return int(round(median(production))) if production else 0

    @computed_field(**HASensor.TIMESTAMP.field("Battery charge optimal start time"))
    @property
    def battery_charge_optimal_start_time(self) -> datetime | None:
        window = self._charge_window()
        if window is None:
            return None

        periods, reachable = window
        if not reachable:
            return self._instant(self._hour_start(self._now_local()))

        return periods[0].time

    @computed_field(**HASensor.DURATION_H.field("Battery charge duration"))
    @property
    def battery_charge_duration(self) -> float | None:
        window = self._charge_window()
        if window is None:
            return None

        return round(len(window[0]) * self.interval_minutes / 60, 2)

    @computed_field(**HABinarySensor.STATUS.field("Battery charge target reachable"))
    @property
    def battery_charge_target_reachable(self) -> bool | None:
        window = self._charge_window()
        return window[1] if window else None

    def _charge_window(self) -> tuple[list[Period], bool] | None:
        if not self.battery_charge_needed_wh or self.battery_charge_needed_wh <= 0:
            return None

        periods = [
            period
            for period in self._remaining_periods_today()
            if period.value > self.production_threshold_wh
        ]

        if not periods:
            return None

        anchor = max(range(len(periods)), key=lambda index: periods[index].value)
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
                return periods[first : last + 1], False

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

        return periods[first : last + 1], True

    def _is_wall(self, left: Period, right: Period) -> bool:
        gap = right.time - left.time
        return gap.total_seconds() > self.interval_minutes * 60

    def _charged(self, period: Period) -> float:
        if self.battery_charge_slot_cap_wh is None:
            return float(period.value)

        return min(float(period.value), self.battery_charge_slot_cap_wh)

    def _remaining_periods_today(self) -> list[Period]:
        hour_start = self._instant(self._hour_start(self._now_local()))
        return [period for period in self._periods_today() if period.time >= hour_start]

    def _periods_today(self) -> list[Period]:
        today = self._now_local().date()
        return sorted(
            (
                Period(period.instant, energy)
                for period, energy in self._periods()
                if period.local.date() == today
            ),
            key=lambda period: period.time,
        )

    def _peak_period_today(self) -> Period | None:
        producing = [period for period in self._periods_today() if period.value > 0]
        if not producing:
            return None

        return max(producing, key=lambda period: period.value)

    def _production_periods_today(self) -> list[int]:
        return [
            period.value
            for period in self._periods_today()
            if period.value > self.production_threshold_wh
        ]

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self._default_homeassistant_device_info("Forecast")
