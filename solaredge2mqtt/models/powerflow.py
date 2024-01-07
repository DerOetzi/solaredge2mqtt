from __future__ import annotations

from typing import Dict, Optional, ClassVar

from solaredge2mqtt.models.base import InfluxDBModel
from solaredge2mqtt.models.modbus import SunSpecBattery, SunSpecInverter, SunSpecMeter


class InverterPowerflow(InfluxDBModel):
    power: int
    consumption: int
    production: int
    pv_production: int
    battery_production: int

    def __init__(
        self,
        inverter_data: SunSpecInverter,
        battery: BatteryPowerflow,
    ):
        power = int(inverter_data.ac.power.actual)

        if power >= 0:
            consumption = 0
            production = power
            if battery.discharge > 0:
                battery_factor = battery.discharge / inverter_data.dc.power
                battery_production = int(round(production * battery_factor))
                battery_production = min(battery_production, production)
                pv_production = production - battery_production
            else:
                battery_production = 0
                pv_production = production

        else:
            consumption = int(abs(power))
            production = 0
            pv_production = 0
            battery_production = 0

        super().__init__(
            power=power,
            consumption=consumption,
            production=production,
            pv_production=pv_production,
            battery_production=battery_production,
        )

    @property
    def is_valid(self) -> bool:
        return all(
            [
                self.consumption >= 0.0,
                self.production >= 0.0,
                self.pv_production >= 0.0,
                self.battery_production >= 0.0,
            ]
        )


class GridPowerflow(InfluxDBModel):
    power: int
    consumption: int
    delivery: int

    def __init__(self, meters_data: Dict[str, SunSpecMeter]):
        grid = 0
        for meter in meters_data.values():
            if "Import" in meter.info.option and "Export" in meter.info.option:
                grid += meter.power.actual

        if grid >= 0:
            consumption = 0
            delivery = grid
        else:
            consumption = int(abs(grid))
            delivery = 0

        super().__init__(power=grid, consumption=consumption, delivery=delivery)

    @property
    def is_valid(self) -> bool:
        return all([self.consumption >= 0.0, self.delivery >= 0.0])


class BatteryPowerflow(InfluxDBModel):
    power: int
    charge: int
    discharge: int

    def __init__(self, batteries_data: Dict[str, SunSpecBattery]):
        batteries_power = 0
        for battery in batteries_data.values():
            batteries_power += battery.power

        if batteries_power >= 0:
            charge = batteries_power
            discharge = 0
        else:
            charge = 0
            discharge = abs(batteries_power)

        super().__init__(power=batteries_power, charge=charge, discharge=discharge)

    @property
    def is_valid(self) -> bool:
        return all([self.charge >= 0.0, self.discharge >= 0.0])


class ConsumerPowerflow(InfluxDBModel):
    house: int
    evcharger: int = 0
    inverter: int

    total: int

    used_pv_production: int
    used_battery_production: int

    def __init__(
        self, inverter: InverterPowerflow, grid: GridPowerflow, evcharger: int
    ):
        house = int(abs(grid.power - inverter.power))
        if evcharger < house:
            house -= evcharger
        else:
            # Happens when EV Charger starts up and meters are not yet updated
            evcharger = 0

        total = house + evcharger + inverter.consumption

        if inverter.pv_production > inverter.production - grid.delivery:
            pv_production = inverter.pv_production - grid.delivery
        else:
            pv_production = inverter.pv_production

        if inverter.battery_production > inverter.production - grid.delivery:
            battery_production = inverter.battery_production - grid.delivery
        else:
            battery_production = inverter.battery_production

        super().__init__(
            house=house,
            evcharger=evcharger,
            used_pv_production=pv_production,
            used_battery_production=battery_production,
            inverter=inverter.consumption,
            total=total,
        )

    @property
    def is_valid(self) -> bool:
        return all(
            [
                self.house >= 0.0,
                self.evcharger >= 0.0,
                self.inverter >= 0.0,
                self.used_pv_production >= 0.0,
                self.used_battery_production >= 0.0,
                self.total >= 0.0,
                self.total >= self.used_battery_production + self.used_pv_production,
            ]
        )


class Powerflow(InfluxDBModel):
    pv_production: int
    inverter: InverterPowerflow
    grid: GridPowerflow
    battery: BatteryPowerflow
    consumer: ConsumerPowerflow

    last_powerflow: ClassVar[Powerflow] = None

    def __init__(
        self,
        inverter_data: SunSpecInverter,
        meters_data: Dict[str, SunSpecMeter],
        batteries_data: Dict[str, SunSpecBattery],
        evcharger: Optional[int] = 0,
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

    def is_valid(self) -> bool:
        return all(
            [
                self.inverter.is_valid,
                self.grid.is_valid,
                self.battery.is_valid,
                self.consumer.is_valid,
                self.pv_production >= 0,
                self.grid.delivery <= self.inverter.production,
            ]
        )

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
