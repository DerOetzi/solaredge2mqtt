from __future__ import annotations

from typing import ClassVar

from influxdb_client import Point
from pydantic import Field, computed_field

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models.base import Solaredge2MQTTBaseModel
from solaredge2mqtt.models.modbus import (SunSpecBattery, SunSpecInverter,
                                          SunSpecMeter)


class InverterPowerflow(Solaredge2MQTTBaseModel):
    power: int
    dc_power: int
    battery_factor: float = Field(exclude=True)

    def __init__(
        self,
        inverter_data: SunSpecInverter,
        battery: BatteryPowerflow,
    ):
        power = int(inverter_data.ac.power.actual)
        dc_power = int(inverter_data.dc.power)
        battery_factor = 0.0

        if power > 0 and battery.discharge > 0:
            battery_factor = battery.discharge / dc_power

        super().__init__(
            power=power,
            dc_power=dc_power,
            battery_factor=battery_factor,
        )

    @computed_field
    @property
    def consumption(self) -> int:
        return abs(self.power) if self.power < 0 else 0

    @computed_field
    @property
    def production(self) -> int:
        return self.power if self.power > 0 else 0

    @computed_field
    @property
    def battery_production(self) -> int:
        battery_production = 0
        if self.production > 0 and self.battery_factor > 0:
            battery_production = int(round(self.production * self.battery_factor))
            battery_production = min(battery_production, self.production)
        return battery_production

    @computed_field
    @property
    def pv_production(self) -> int:
        return self.production - self.battery_production

    @property
    def is_valid(self) -> bool:
        valid = False
        if self.consumption < 0:
            logger.warning("Inverter consumption is negative")
        elif self.production < 0:
            logger.warning("Inverter production is negative")
        elif self.pv_production < 0:
            logger.warning("Inverter PV production is negative")
        elif self.battery_production < 0:
            logger.warning("Inverter battery production is negative")
        else:
            valid = True

        return valid


class GridPowerflow(Solaredge2MQTTBaseModel):
    power: int

    def __init__(self, meters_data: dict[str, SunSpecMeter]):
        grid = 0
        for meter in meters_data.values():
            if "Import" in meter.info.option and "Export" in meter.info.option:
                grid += meter.power.actual

        super().__init__(power=grid)

    @computed_field
    @property
    def consumption(self) -> int:
        return abs(self.power) if self.power < 0 else 0

    @computed_field
    @property
    def delivery(self) -> int:
        return self.power if self.power > 0 else 0

    @property
    def is_valid(self) -> bool:
        valid = False
        if self.consumption < 0:
            logger.warning("Grid consumption is negative")
        elif self.delivery < 0:
            logger.warning("Grid delivery is negative")
        else:
            valid = True

        return valid


class BatteryPowerflow(Solaredge2MQTTBaseModel):
    power: int

    def __init__(self, batteries_data: dict[str, SunSpecBattery]):
        batteries_power = 0
        for battery in batteries_data.values():
            batteries_power += battery.power

        super().__init__(power=batteries_power)

    @computed_field
    @property
    def charge(self) -> int:
        return self.power if self.power > 0 else 0

    @computed_field
    @property
    def discharge(self) -> int:
        return abs(self.power) if self.power < 0 else 0

    @property
    def is_valid(self) -> bool:
        valid = False
        if self.charge < 0:
            logger.warning("Battery charge is negative")
        elif self.discharge < 0:
            logger.warning("Battery discharge is negative")
        else:
            valid = True

        return valid


class ConsumerPowerflow(Solaredge2MQTTBaseModel):
    house: int
    evcharger: int = 0
    inverter: int

    used_production: int
    battery_factor: float = Field(exclude=True)

    def __init__(
        self, inverter: InverterPowerflow, grid: GridPowerflow, evcharger: int
    ):
        house = int(abs(grid.power - inverter.power)) - evcharger

        battery_factor = inverter.battery_factor

        if inverter.production > 0 and inverter.production > grid.delivery:
            used_production = inverter.production - grid.delivery
        else:
            used_production = 0

        super().__init__(
            house=house,
            evcharger=evcharger,
            inverter=inverter.consumption,
            used_production=used_production,
            battery_factor=battery_factor,
        )

    @computed_field
    @property
    def total(self) -> int:
        return self.house + self.evcharger + self.inverter

    @computed_field
    @property
    def used_battery_production(self) -> int:
        battery_production = 0
        if self.used_production > 0 and self.battery_factor > 0:
            battery_production = int(round(self.used_production * self.battery_factor))
            battery_production = min(battery_production, self.used_production)
        return battery_production

    @computed_field
    @property
    def used_pv_production(self) -> int:
        return self.used_production - self.used_battery_production

    @property
    def is_valid(self) -> bool:
        valid = False
        if self.house < 0:
            logger.warning("Consumer house is negative")
        elif self.evcharger < 0:
            logger.warning("Consumer evcharger is negative")
        elif self.inverter < 0:
            logger.warning("Consumer inverter is negative")
        elif self.used_production < 0:
            logger.warning("Consumer used production is negative")
        elif self.used_pv_production < 0:
            logger.warning("Consumer used PV production is negative")
        elif self.used_battery_production < 0:
            logger.warning("Consumer used battery production is negative")
        elif self.total < 0:
            logger.warning("Consumer total is negative")
        elif self.total < self.used_production:
            logger.warning("Consumer total is less than used production")
        else:
            valid = True

        return valid


class Powerflow(Solaredge2MQTTBaseModel):
    pv_production: int
    inverter: InverterPowerflow
    grid: GridPowerflow
    battery: BatteryPowerflow
    consumer: ConsumerPowerflow

    last_powerflow: ClassVar[Powerflow] = None

    def __init__(
        self,
        inverter_data: SunSpecInverter,
        meters_data: dict[str, SunSpecMeter],
        batteries_data: dict[str, SunSpecBattery],
        evcharger: int = 0,
    ):
        grid = GridPowerflow(meters_data)
        battery = BatteryPowerflow(batteries_data)

        if inverter_data.ac.power.actual > 0:
            pv_production = int(inverter_data.dc.power + battery.power)
            if pv_production < 0:
                pv_production = 0
        else:
            pv_production = 0

        inverter = InverterPowerflow(inverter_data, battery)

        consumer = ConsumerPowerflow(inverter, grid, evcharger)

        super().__init__(
            pv_production=pv_production,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

    @property
    def is_valid(self) -> bool:
        valid = False

        if self.pv_production < 0:
            logger.warning("PV production is negative")
        elif (
            self.consumer.used_production + self.grid.delivery
            != self.inverter.production
        ):
            logger.warning(
                "Consumer used production + grid delivery is not equal to inverter production"
            )
        else:
            valid = all(
                [
                    self.inverter.is_valid,
                    self.grid.is_valid,
                    self.battery.is_valid,
                    self.consumer.is_valid,
                ]
            )

        return valid

    @classmethod
    def is_not_valid_with_last(cls, powerflow: Powerflow) -> bool:
        check = False

        if cls.last_powerflow is not None:
            check = all(
                [
                    cls.last_powerflow.pv_production == 0
                    and powerflow.pv_production > 100,
                ]
            )

        cls.last_powerflow = powerflow

        return check

    def prepare_point(self, measurement: str = "powerflow_raw") -> Point:
        point = Point(measurement)
        for key, value in self.model_dump_influxdb().items():
            point.field(key, value)

        return point
