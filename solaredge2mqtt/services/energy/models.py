from __future__ import annotations

from datetime import datetime

from pydantic import Field, computed_field

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.models import EnumModel, Solaredge2MQTTBaseModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantEntityType as EntityType,
)
from solaredge2mqtt.services.models import Component


class HistoricBaseModel(Component):
    SOURCE = "energy"

    info: HistoricInfo

    def __init__(self, data: dict, period: HistoricPeriod, **kwargs):
        super().__init__(
            info=HistoricInfo(period=period, start=data["_start"], stop=data["_stop"]),
            **kwargs,
        )

    def mqtt_topic(self) -> str:
        return f"{self.SOURCE}/{self.info.period.topic}"

    def __str__(self) -> str:
        return f"{self.SOURCE}: {self.info.period}"


class HistoricEnergy(HistoricBaseModel):
    pv_production: float = Field(**EntityType.ENERGY_KWH.field("PV production"))
    inverter: InverterEnergy = Field(title="Inverter")
    grid: GridEnergy = Field(title="Grid")
    battery: BatteryEnergy = Field(title="Battery")
    consumer: ConsumerEnergy = Field(title="Consumer")
    money: HistoricMoney | None = Field(None, title="Money")

    def __init__(
        self,
        energy_data: dict,
        period: HistoricPeriod,
    ):
        logger.trace(energy_data)
        pv_production = energy_data["pv_production"]

        subclass_values: dict[str, dict[str, float]] = {}

        for key, value in energy_data.items():
            keys = key.split("_")
            if len(keys) < 2:
                continue

            if keys[0] in ["consumer", "inverter", "grid", "battery", "money"]:
                if keys[0] not in subclass_values:
                    subclass_values[keys[0]] = {}

                subclass_values[keys[0]]["_".join(keys[1:])] = round(value, 3)

        logger.debug(subclass_values["consumer"])

        super().__init__(
            period=period,
            data=energy_data,
            pv_production=round(pv_production, 3),
            inverter=InverterEnergy(**subclass_values["inverter"]),
            grid=GridEnergy(**subclass_values["grid"]),
            battery=BatteryEnergy(**subclass_values["battery"]),
            consumer=ConsumerEnergy(**subclass_values["consumer"]),
            money=(
                HistoricMoney(**subclass_values["money"])
                if "money" in subclass_values
                else None
            ),
        )

    @computed_field(title="Self consumption rate")
    @property
    def self_consumption_rates(self) -> SelfConsumptionRate:
        return SelfConsumptionRate(self)

    @computed_field(title="Self sufficiency rate")
    @property
    def self_sufficiency_rates(self) -> SelfSufficiencyRate:
        return SelfSufficiencyRate(self)

    def homeassistant_device_info(self) -> dict[str, any]:
        return self._default_homeassistant_device_info(
            f"Energy - {self.info.period.title}"
        )


class HistoricMoney(Solaredge2MQTTBaseModel):
    delivered: float = Field(**EntityType.MONETARY.field("Delivered"))
    saved: float = Field(**EntityType.MONETARY.field("Saved"))
    consumed: float = Field(**EntityType.MONETARY.field("Consumed"))
    price_in: float = Field(exclude=True)
    price_out: float = Field(exclude=True)

    @computed_field(**EntityType.MONETARY.field("Balance grid"))
    @property
    def balance_grid(self) -> float:
        return round(self.delivered - self.consumed, 3)

    @computed_field(**EntityType.MONETARY.field("Balance total"))
    @property
    def balance_total(self) -> float:
        return round(self.balance_grid + self.saved, 3)


class HistoricInfo(Solaredge2MQTTBaseModel):
    period: HistoricPeriod
    start: datetime
    stop: datetime


class HistoricQuery(EnumModel):
    ACTUAL = "actual_unit"
    LAST = "historic_unit"

    def __init__(self, query: str) -> None:
        self._query: str = query

    @property
    def query(self) -> str:
        return self._query


class HistoricPeriod(EnumModel):
    LAST_HOUR = (
        "last_hour",
        "Last hour",
        "1h",
        HistoricQuery.LAST,
        True,
    )
    TODAY = "today", "Today", "1d", HistoricQuery.ACTUAL, True
    YESTERDAY = (
        "yesterday",
        "Yesterday",
        "1d",
        HistoricQuery.LAST,
        True,
    )
    THIS_WEEK = "this_week", "This week", "1w", HistoricQuery.ACTUAL, False
    LAST_WEEK = "last_week", "Last week", "1w", HistoricQuery.LAST, False
    THIS_MONTH = (
        "this_month",
        "This month",
        "1mo",
        HistoricQuery.ACTUAL,
        True,
    )
    LAST_MONTH = "last_month", "Last month", "1mo", HistoricQuery.LAST, False
    THIS_YEAR = (
        "this_year",
        "This year",
        "1y",
        HistoricQuery.ACTUAL,
        True,
    )
    LAST_YEAR = "last_year", "Last year", "1y", HistoricQuery.LAST, False
    LIFETIME = (
        "lifetime",
        "Lifetime",
        "99y",
        HistoricQuery.ACTUAL,
        True,
    )

    def __init__(
        self,
        topic: str,
        title: str,
        unit: str,
        query: HistoricQuery,
        auto_discovery: bool,
    ) -> None:
        self._topic: str = topic
        self._title: str = title
        self._unit: str = unit
        self._query: HistoricQuery = query
        self._auto_discovery: bool = auto_discovery

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def title(self) -> str:
        return self._title

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def query(self) -> HistoricQuery:
        return self._query

    @property
    def auto_discovery(self) -> bool:
        return self._auto_discovery


class InverterEnergy(Solaredge2MQTTBaseModel):
    production: float = Field(**EntityType.ENERGY_KWH.field("Production"))
    consumption: float = Field(**EntityType.ENERGY_KWH.field("Consumption"))
    dc_power: float = Field(**EntityType.POWER_W.field("DC production"))
    pv_production: float = Field(**EntityType.ENERGY_KWH.field("PV production"))
    battery_production: float = Field(
        **EntityType.ENERGY_KWH.field("Battery production")
    )


class GridEnergy(Solaredge2MQTTBaseModel):
    delivery: float = Field(**EntityType.ENERGY_KWH.field("Delivery"))
    consumption: float = Field(**EntityType.ENERGY_KWH.field("Consumption"))


class BatteryEnergy(Solaredge2MQTTBaseModel):
    charge: float = Field(**EntityType.ENERGY_KWH.field("Charge"))
    discharge: float = Field(**EntityType.ENERGY_KWH.field("Discharge"))


class ConsumerEnergy(Solaredge2MQTTBaseModel):
    house: float = Field(**EntityType.ENERGY_KWH.field("House"))
    evcharger: float = Field(**EntityType.ENERGY_KWH.field("EV-Charger"))
    inverter: float = Field(**EntityType.ENERGY_KWH.field("Inverter"))

    total: float = Field(**EntityType.ENERGY_KWH.field("Total"))

    used_production: float = Field(**EntityType.ENERGY_KWH.field("Used production"))
    used_pv_production: float = Field(
        **EntityType.ENERGY_KWH.field("Used PV production")
    )
    used_battery_production: float = Field(
        **EntityType.ENERGY_KWH.field("Used battery production")
    )


class SelfConsumptionRate(Solaredge2MQTTBaseModel):
    grid: int = Field(**EntityType.PERCENTAGE.field("Grid"))
    battery: int = Field(**EntityType.PERCENTAGE.field("Battery"))
    pv: int = Field(**EntityType.PERCENTAGE.field("PV"))
    total: int = Field(**EntityType.PERCENTAGE.field("Total"))

    def __init__(self, energy: HistoricEnergy):
        if energy.inverter.production > 0:
            grid_rate = int(
                round(energy.grid.delivery / energy.inverter.production * 100)
            )
            battery_rate = int(
                round(
                    energy.consumer.used_battery_production
                    / energy.inverter.production
                    * 100
                )
            )
            pv_rate = 100 - grid_rate - battery_rate
            total = battery_rate + pv_rate
        else:
            grid_rate = 0
            battery_rate = 0
            pv_rate = 0
            total = 0

        super().__init__(
            grid=grid_rate,
            battery=battery_rate,
            pv=pv_rate,
            total=total,
        )


class SelfSufficiencyRate(Solaredge2MQTTBaseModel):
    grid: int = Field(**EntityType.PERCENTAGE.field("Grid"))
    battery: int = Field(**EntityType.PERCENTAGE.field("Battery"))
    pv: int = Field(**EntityType.PERCENTAGE.field("PV"))
    total: int = Field(**EntityType.PERCENTAGE.field("Total"))

    def __init__(self, energy: HistoricEnergy):
        if energy.consumer.total > 0:
            grid_rate = int(
                round(energy.grid.consumption / energy.consumer.total * 100)
            )
            battery_rate = int(
                round(
                    energy.consumer.used_battery_production
                    / energy.consumer.total
                    * 100
                )
            )
            pv_rate = 100 - grid_rate - battery_rate
            total = battery_rate + pv_rate
        else:
            grid_rate = 0
            battery_rate = 0
            pv_rate = 0
            total = 0

        super().__init__(
            grid=grid_rate,
            battery=battery_rate,
            pv=pv_rate,
            total=total,
        )
