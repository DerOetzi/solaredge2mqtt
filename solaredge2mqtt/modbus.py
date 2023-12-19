import json
from typing import Dict, Tuple

from solaredge_modbus import Inverter

from solaredge2mqtt.logging import LOGGING_DEVICE_INFO, logger
from solaredge2mqtt.models import (
    PowerFlow,
    SunSpecBattery,
    SunSpecInverter,
    SunSpecMeter,
)
from solaredge2mqtt.settings import ServiceSettings

SunSpecRawData = Dict[str, str | int]


class Modbus:
    inverter: Inverter

    def __init__(self, settings: ServiceSettings):
        self.inverter = Inverter(
            host=settings.modbus_host,
            port=settings.modbus_port,
            timeout=settings.modbus_timeout,
            unit=settings.modbus_unit,
        )

        logger.info(
            "Using SolarEdge inverter via modbus: {host}:{port}",
            host=settings.modbus_host,
            port=settings.modbus_port,
        )

    def loop(
        self,
    ) -> Tuple[SunSpecInverter, Dict[str, SunSpecMeter], Dict[str, SunSpecBattery]]:
        inverter_raw, meters_raw, batteries_raw = self._get_raw_data()

        inverter_data = self._map_inverter(inverter_raw)
        meters_data = self._map_meters(meters_raw)
        batteries_data = self._map_batteries(batteries_raw)

        return inverter_data, meters_data, batteries_data

    def _get_raw_data(
        self,
    ) -> Tuple[SunSpecRawData, Dict[str, SunSpecRawData], Dict[str, SunSpecRawData]]:
        inverter_raw = self.inverter.read_all()
        meters_raw = {
            meter_key: meter_obj.read_all()
            for meter_key, meter_obj in self.inverter.meters().items()
        }
        batteries_raw = {
            battery_key: battery_obj.read_all()
            for battery_key, battery_obj in self.inverter.batteries().items()
        }

        return inverter_raw, meters_raw, batteries_raw

    def _map_inverter(self, inverter_raw: SunSpecRawData) -> SunSpecInverter:
        logger.debug(
            "Inverter raw:\n{raw}",
            raw=json.dumps(inverter_raw, indent=4),
        )

        inverter_data = SunSpecInverter(inverter_raw)
        logger.debug(inverter_data)
        logger.info(
            LOGGING_DEVICE_INFO
            + ": {status}, AC {power_ac} W, DC {power_dc} W, {energy_total} kWh",
            device="Inverter",
            info=inverter_data.info,
            status=inverter_data.status,
            power_ac=inverter_data.ac.power.power,
            power_dc=inverter_data.dc.power,
            energy_total=round(inverter_data.energy_total / 1000, 2),
        )

        return inverter_data

    def _map_meters(
        self, meters_raw: Dict[str, SunSpecRawData]
    ) -> Dict[str, SunSpecInverter]:
        meters = {}
        for meter_key, meter_raw in meters_raw.items():
            logger.debug(
                "Meter {meter} raw:\n{raw}",
                meter=meter_key,
                raw=json.dumps(meter_raw, indent=4),
            )

            meter_data = SunSpecMeter(meter_raw)
            logger.debug(meter_data)
            logger.info(
                LOGGING_DEVICE_INFO + ": {power} W",
                device=meter_key,
                info=meter_data.info,
                power=meter_data.power.power,
            )

            meters[meter_key] = meter_data

        return meters

    def _map_batteries(
        self, batteries_raw: Dict[str, SunSpecRawData]
    ) -> Dict[str, SunSpecInverter]:
        batteries = {}
        for battery_key, battery_raw in batteries_raw.items():
            logger.debug(
                "Battery {battery} raw:\n{raw}",
                battery=battery_key,
                raw=json.dumps(battery_raw, indent=4),
            )

            battery_data = SunSpecBattery(battery_raw)
            logger.debug(battery_data)
            logger.info(
                LOGGING_DEVICE_INFO + ": {power} W, {state_of_charge} %",
                device=battery_key,
                info=battery_data.info,
                power=battery_data.power,
                state_of_charge=battery_data.state_of_charge,
            )

            batteries[battery_key] = battery_data

        return batteries

    @staticmethod
    def calc_powerflow(
        inverter: SunSpecInverter,
        meters: Dict[str, SunSpecMeter],
        batteries: Dict[str, SunSpecBattery],
    ) -> PowerFlow:
        """
        Calculates the power flow in the system by summing the power of all meters and batteries.
        It considers both import and export options for each meter in the calculation.
        Returns a PowerFlow object representing the total power flow in the system.
        """

        grid = 0
        for meter in meters.values():
            if "Import" in meter.info.option and "Export" in meter.info.option:
                grid += meter.power.power

        batteries_power = 0
        for battery in batteries.values():
            batteries_power += battery.power

        if inverter.dc.power > 0:
            pv_production = inverter.dc.power + batteries_power
            if pv_production < 0:
                pv_production = 0
            inverter_consumption = inverter.dc.power - inverter.ac.power.power
            inverter_delivery = inverter.ac.power.power
        else:
            pv_production = 0
            inverter_consumption = abs(inverter.ac.power.power)
            inverter_delivery = 0

        inverter = inverter.ac.power.power

        if grid >= 0:
            grid_consumption = 0
            grid_delivery = grid
        else:
            grid_consumption = abs(grid)
            grid_delivery = 0

        battery = batteries_power
        if battery >= 0:
            battery_charge = battery
            battery_discharge = 0
        else:
            battery_charge = 0
            battery_discharge = abs(battery)

        house_consumption = int(abs(grid - inverter))

        powerflow = PowerFlow(
            pv_production=int(pv_production),
            inverter=int(inverter),
            inverter_consumption=int(inverter_consumption),
            inverter_delivery=int(inverter_delivery),
            house_consumption=int(house_consumption),
            grid=int(grid),
            grid_consumption=int(grid_consumption),
            grid_delivery=int(grid_delivery),
            battery=int(battery),
            battery_charge=int(battery_charge),
            battery_discharge=int(battery_discharge),
        )

        logger.debug(powerflow)
        logger.info(
            "Powerflow: PV {pv_production} W, Inverter {inverter} W, House {house_consumption} W, "
            + "Grid {grid} W, Battery {battery} W",
            pv_production=powerflow.pv_production,
            inverter=powerflow.inverter,
            house_consumption=powerflow.house_consumption,
            grid=powerflow.grid,
            battery=powerflow.battery,
        )

        return powerflow
