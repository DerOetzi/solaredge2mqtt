from __future__ import annotations

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

__all__ = ["Forecast"]

#: The interval the published forecast covers per period.
INTERVAL_MINUTES = 60


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
        peak = self._peak_slot_today()
        return peak[0] if peak else None

    @computed_field(**HASensor.ENERGY_WH.field("Energy production peak today"))
    @property
    def energy_peak_today(self) -> int:
        peak = self._peak_slot_today()
        return peak[1] if peak else 0

    @computed_field(**HASensor.ENERGY_WH.field("Energy production average today"))
    @property
    def energy_average_today(self) -> int:
        production = self._production_slots_today()
        return int(round(mean(production))) if production else 0

    @computed_field(**HASensor.ENERGY_WH.field("Energy production median today"))
    @property
    def energy_median_today(self) -> int:
        production = self._production_slots_today()
        return int(round(median(production))) if production else 0

    @computed_field(**HASensor.TIMESTAMP.field("Battery charge optimal start time"))
    @property
    def battery_charge_optimal_start_time(self) -> datetime | None:
        window = self._charge_window()
        if window is None:
            return None

        slots, reachable = window
        if not reachable:
            return self._instant(self._hour_start(self._now_local()))

        return slots[0][0]

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

    def _charge_window(self) -> tuple[list[tuple[datetime, int]], bool] | None:
        if not self.battery_charge_needed_wh or self.battery_charge_needed_wh <= 0:
            return None

        slots = [
            slot
            for slot in self._remaining_slots_today()
            if slot[1] > self.production_threshold_wh
        ]

        if not slots:
            return None

        anchor = slots.index(max(slots, key=lambda slot: slot[1]))
        first, last = anchor, anchor
        charged = self._charged(slots[anchor][1])

        while charged < self.battery_charge_needed_wh:
            before = slots[first - 1] if first > 0 else None
            after = slots[last + 1] if last + 1 < len(slots) else None

            if before is not None and self._is_wall(slots, first - 1, first):
                before = None
            if after is not None and self._is_wall(slots, last, last + 1):
                after = None

            if before is None and after is None:
                return slots[first : last + 1], False

            if before is None:
                take_before = False
            elif after is None:
                take_before = True
            elif before[1] <= after[1]:
                take_before = False
            else:
                take_before = (
                    charged + self._charged(before[1]) <= self.battery_charge_needed_wh
                )

            if take_before:
                first -= 1
                charged += self._charged(slots[first][1])
            else:
                last += 1
                charged += self._charged(slots[last][1])

        return slots[first : last + 1], True

    def _is_wall(
        self, slots: list[tuple[datetime, int]], left: int, right: int
    ) -> bool:
        gap = slots[right][0] - slots[left][0]
        return gap.total_seconds() > self.interval_minutes * 60

    def _charged(self, energy: int) -> float:
        if self.battery_charge_slot_cap_wh is None:
            return float(energy)

        return min(float(energy), self.battery_charge_slot_cap_wh)

    def _remaining_slots_today(self) -> list[tuple[datetime, int]]:
        now = self._now_local()
        hour_start = self._instant(self._hour_start(now))
        return [slot for slot in self._slots_today() if slot[0] >= hour_start]

    def _slots_today(self) -> list[tuple[datetime, int]]:
        today = self._now_local().date()
        return sorted(
            (period.instant, energy)
            for period, energy in self._periods()
            if period.local.date() == today
        )

    def _peak_slot_today(self) -> tuple[datetime, int] | None:
        producing = [slot for slot in self._slots_today() if slot[1] > 0]
        if not producing:
            return None

        return max(producing, key=lambda slot: slot[1])

    def _production_slots_today(self) -> list[int]:
        return [
            energy
            for _, energy in self._slots_today()
            if energy > self.production_threshold_wh
        ]

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self._default_homeassistant_device_info("Forecast")
