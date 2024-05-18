from datetime import datetime

from pydantic import computed_field

from solaredge2mqtt.core.models import EnumModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantEntityType as EntityType,
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

    power_period: dict[datetime, int]
    energy_period: dict[datetime, int]

    @computed_field(**EntityType.ENERGY_WH.field("Energy production today"))
    @property
    def energy_today(self) -> int:
        return sum(self._energy_today)

    @computed_field(**EntityType.ENERGY_WH.field("Energy production remaining today"))
    @property
    def energy_today_remaining(self) -> int:
        return sum(self._energy_today[self._current_hour() :])

    @computed_field(**EntityType.ENERGY_WH.field("Energy production current hour"))
    def energy_current_hour(self) -> int:
        return self._energy_today[self._current_hour()]

    @computed_field(**EntityType.ENERGY_WH.field("Energy production next hour"))
    def energy_next_hour(self) -> int:
        if self._current_hour() == 23:
            energy_next_hour = self._energy_tomorrow[0]
        else:
            energy_next_hour = self._energy_today[self._current_hour() + 1]

        return energy_next_hour

    @computed_field(**EntityType.ENERGY_WH.field("Energy production tomorrow"))
    @property
    def energy_tomorrow(self) -> int:
        return sum(self._energy_tomorrow)

    @property
    def _energy_today(self) -> list[int]:
        return [*self.energy_period.values()][:24]

    @property
    def _energy_tomorrow(self) -> list[int]:
        return [*self.energy_period.values()][24:]

    @staticmethod
    def _current_hour() -> int:
        return datetime.now().hour

    @classmethod
    # pylint: disable=arguments-differ
    def model_json_schema(cls, mode: str = "serialization") -> dict[str, any]:
        schema = super().model_json_schema(mode=mode)
        schema["properties"].pop("power_period", None)
        schema["properties"].pop("energy_period", None)
        return schema

    def homeassistant_device_info(self) -> dict[str, any]:
        return self._default_homeassistant_device_info("Forecast")
