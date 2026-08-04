from __future__ import annotations

from datetime import datetime
from typing import Any

from pvlearn.forecaster import ForecasterType
from pvlearn.result import ForecastResult
from pydantic import computed_field
from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import Component

__all__ = ["Forecast", "ForecasterType"]


class Forecast(Component, ForecastResult):
    COMPONENT = "forecast"

    power_period: SkipJsonSchema[dict[datetime, int]]
    energy_period: SkipJsonSchema[dict[datetime, int]]
    battery_charge_needed_wh: SkipJsonSchema[float | None] = None

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

    @staticmethod
    def _now() -> datetime:
        return datetime.now().astimezone()

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self._default_homeassistant_device_info("Forecast")
