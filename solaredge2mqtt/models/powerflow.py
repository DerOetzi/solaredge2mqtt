from __future__ import annotations

from typing import Dict, Optional

from solaredge2mqtt.models.base import InfluxDBModel
from solaredge2mqtt.models.modbus import SunSpecBattery, SunSpecInverter, SunSpecMeter


class InverterPowerflow(InfluxDBModel):
    power: int
    consumption: int
    production: int
    pv_production: int
    battery_production: int

    @staticmethod
    def calc(
        inverter_data: SunSpecInverter,
        battery: BatteryPowerflow,
    ) -> InverterPowerflow:
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

        return InverterPowerflow(
            power=power,
            consumption=consumption,
            production=production,
            pv_production=pv_production,
            battery_production=battery_production,
        )


class GridPowerflow(InfluxDBModel):
    power: int
    consumption: int
    delivery: int

    @staticmethod
    def calc(meters_data: Dict[str, SunSpecMeter]) -> GridPowerflow:
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

        return GridPowerflow(power=grid, consumption=consumption, delivery=delivery)


class BatteryPowerflow(InfluxDBModel):
    power: int
    charge: int
    discharge: int

    @staticmethod
    def calc(batteries_data: Dict[str, SunSpecBattery]) -> BatteryPowerflow:
        batteries_power = 0
        for battery in batteries_data.values():
            batteries_power += battery.power

        if batteries_power >= 0:
            charge = batteries_power
            discharge = 0
        else:
            charge = 0
            discharge = abs(batteries_power)

        return BatteryPowerflow(
            power=batteries_power, charge=charge, discharge=discharge
        )


class ConsumerPowerflow(InfluxDBModel):
    house: int
    evcharger: int = 0
    inverter: int

    total: int

    used_pv_production: int
    used_battery_production: int

    @staticmethod
    def calc(
        inverter: InverterPowerflow, grid: GridPowerflow, evcharger: int
    ) -> ConsumerPowerflow:
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

        return ConsumerPowerflow(
            house=house,
            evcharger=evcharger,
            used_pv_production=pv_production,
            used_battery_production=battery_production,
            inverter=inverter.consumption,
            total=total,
        )

    def is_valid(self) -> bool:
        return self.total >= self.used_battery_production + self.used_pv_production


class Powerflow(InfluxDBModel):
    pv_production: int
    inverter: InverterPowerflow
    grid: GridPowerflow
    battery: BatteryPowerflow
    consumer: ConsumerPowerflow

    @staticmethod
    def calc(
        inverter_data: SunSpecInverter,
        meters_data: Dict[str, SunSpecMeter],
        batteries_data: Dict[str, SunSpecBattery],
        evcharger: Optional[int] = 0,
    ) -> Powerflow:
        grid = GridPowerflow.calc(meters_data)
        battery = BatteryPowerflow.calc(batteries_data)

        if inverter_data.ac.power.actual > 0:
            pv_production = int(inverter_data.dc.power + battery.power)
            if pv_production < 0:
                pv_production = 0
        else:
            pv_production = 0

        inverter = InverterPowerflow.calc(inverter_data, battery)

        consumer = ConsumerPowerflow.calc(inverter, grid, evcharger)

        return Powerflow(
            pv_production=pv_production,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )
