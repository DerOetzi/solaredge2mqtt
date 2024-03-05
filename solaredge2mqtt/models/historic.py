from __future__ import annotations

from datetime import datetime

from pydantic import Field, computed_field

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models.base import EnumModel, Solaredge2MQTTBaseModel


class HistoricBaseModel(Solaredge2MQTTBaseModel):
    info: HistoricInfo

    def __init__(self, data: dict, period: HistoricPeriod, **kwargs):
        super().__init__(
            info=HistoricInfo(period=period, start=data["_start"], stop=data["_stop"]),
            **kwargs,
        )


class HistoricEnergy(HistoricBaseModel):
    pv_production: float
    inverter: InverterEnergy
    grid: GridEnergy
    battery: BatteryEnergy
    consumer: ConsumerEnergy
    money: HistoricMoney | None = Field(None)

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

    @computed_field
    @property
    def self_consumption_rates(self) -> SelfConsumptionRate:
        return SelfConsumptionRate(self)

    @computed_field
    @property
    def self_sufficiency_rates(self) -> SelfSufficiencyRate:
        return SelfSufficiencyRate(self)


class HistoricMoney(Solaredge2MQTTBaseModel):
    earnings: float
    savings: float
    price_in: float = Field(exclude=True)
    price_out: float = Field(exclude=True)


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
    LAST_HOUR = "last_hour", "1h", HistoricQuery.LAST
    TODAY = "today", "1d", HistoricQuery.ACTUAL
    YESTERDAY = "yesterday", "1d", HistoricQuery.LAST
    THIS_WEEK = "this_week", "1w", HistoricQuery.ACTUAL
    LAST_WEEK = "last_week", "1w", HistoricQuery.LAST
    THIS_MONTH = "this_month", "1mo", HistoricQuery.ACTUAL
    LAST_MONTH = "last_month", "1mo", HistoricQuery.LAST
    THIS_YEAR = "this_year", "1y", HistoricQuery.ACTUAL

    def __init__(self, topic: str, unit: str, query: HistoricQuery) -> None:
        self._topic: str = topic
        self._unit: str = unit
        self._query: HistoricQuery = query

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def unit(self) -> str:
        return self._unit

    @property
    def query(self) -> HistoricQuery:
        return self._query


class InverterEnergy(Solaredge2MQTTBaseModel):
    production: float
    consumption: float
    dc_power: float
    pv_production: float
    battery_production: float


class GridEnergy(Solaredge2MQTTBaseModel):
    delivery: float
    consumption: float


class BatteryEnergy(Solaredge2MQTTBaseModel):
    charge: float
    discharge: float


class ConsumerEnergy(Solaredge2MQTTBaseModel):
    house: float
    evcharger: float
    inverter: float

    total: float

    used_production: float
    used_pv_production: float
    used_battery_production: float


class SelfConsumptionRate(Solaredge2MQTTBaseModel):
    grid: int
    battery: int
    pv: int
    total: int

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
    grid: int
    battery: int
    pv: int
    total: int

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
