from datetime import datetime

from pydantic import computed_field

from solaredge2mqtt.models.base import Component, ComponentEvent
from solaredge2mqtt.models.homeassistant import HomeAssistantEntityType as EntityType


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


class ForecastEvent(ComponentEvent):
    pass
