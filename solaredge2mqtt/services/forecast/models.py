from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import computed_field
from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.core.models import EnumModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import Component


class ForecasterType(EnumModel):
    ENERGY = "energy"
    POWER = "power"

    def __init__(self, target_column: str) -> None:
        self._target_column: str = target_column

    @property
    def target_column(self) -> str:
        return self._target_column

    def prepare_value(self, value: float | int) -> float | int:
        if value <= 0:
            prepared = 0
        elif self.target_column == "energy":
            prepared = round(value / 1000, 3)
        else:
            prepared = int(round(value))

        return prepared


class Forecast(Component):
    COMPONENT = "forecast"

    power_period: SkipJsonSchema[dict[datetime, int]]
    energy_period: SkipJsonSchema[dict[datetime, int]]
    battery_charge_needed_wh: SkipJsonSchema[float | None] = None

    @computed_field(**HASensor.ENERGY_WH.field("Energy production today"))
    @property
    def energy_today(self) -> int:
        return sum(self._energy_today)

    @computed_field(**HASensor.ENERGY_WH.field("Energy production remaining today"))
    @property
    def energy_today_remaining(self) -> int:
        return sum(self._energy_today[self._current_hour() :])

    @computed_field(**HASensor.ENERGY_WH.field("Energy production current hour"))
    def energy_current_hour(self) -> int:
        return self._energy_today[self._current_hour()]

    @computed_field(**HASensor.ENERGY_WH.field("Energy production next hour"))
    def energy_next_hour(self) -> int:
        if self._current_hour() == 23:
            energy_next_hour = self._energy_tomorrow[0]
        else:
            energy_next_hour = self._energy_today[self._current_hour() + 1]

        return energy_next_hour

    @computed_field(**HASensor.ENERGY_WH.field("Energy production tomorrow"))
    @property
    def energy_tomorrow(self) -> int:
        return sum(self._energy_tomorrow)

    @computed_field(**HASensor.TIMESTAMP.field("Battery charge optimal start time"))
    @property
    def battery_charge_optimal_start_time(self) -> datetime | None:
        if not self.battery_charge_needed_wh or self.battery_charge_needed_wh <= 0:
            return None

        now = self._now().replace(minute=0, second=0, microsecond=0)
        upcoming_slots = [
            (slot_time, slot_energy)
            for slot_time, slot_energy in self.energy_period.items()
            if slot_time >= now
        ]

        if not upcoming_slots:
            return None

        strongest_first = sorted(upcoming_slots, key=lambda slot: slot[1], reverse=True)

        accumulated = 0
        selected_times: list[datetime] = []
        for slot_time, slot_energy in strongest_first:
            if accumulated >= self.battery_charge_needed_wh:
                break
            accumulated += slot_energy
            selected_times.append(slot_time)

        if accumulated < self.battery_charge_needed_wh:
            return None

        return min(selected_times)

    @property
    def _energy_today(self) -> list[int]:
        return [*self.energy_period.values()][:24]

    @property
    def _energy_tomorrow(self) -> list[int]:
        return [*self.energy_period.values()][24:]

    @staticmethod
    def _current_hour() -> int:
        return datetime.now().hour

    @staticmethod
    def _now() -> datetime:
        return datetime.now().astimezone()

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self._default_homeassistant_device_info("Forecast")
