import json
from typing import Dict, Tuple

from pymodbus.exceptions import ModbusException

from solaredge_modbus import Inverter

from solaredge2mqtt.logging import LOGGING_DEVICE_INFO, logger
from solaredge2mqtt.models import (
    Powerflow,
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

    async def loop(
        self,
    ) -> Tuple[
        SunSpecInverter | None,
        Dict[str, SunSpecMeter] | None,
        Dict[str, SunSpecBattery | None],
    ] | None:
        inverter_data = None
        meters_data = None
        batteries_data = None

        try:
            inverter_raw, meters_raw, batteries_raw = self._get_raw_data()

            inverter_data = self._map_inverter(inverter_raw)
            meters_data = self._map_meters(meters_raw)
            batteries_data = self._map_batteries(batteries_raw)
        except ModbusException as error:
            logger.error(
                "Exception while reading data from modbus: {exception}",
                exception=error,
            )

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
            + ": {status}, AC {power_ac} W, DC {power_dc} W, {energytotal} kWh",
            device="Inverter",
            info=inverter_data.info,
            status=inverter_data.status,
            power_ac=inverter_data.ac.power.actual,
            power_dc=inverter_data.dc.power,
            energytotal=round(inverter_data.energytotal / 1000, 2),
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
                LOGGING_DEVICE_INFO + ": {power} W, {consumption} kWh, {delivery} kWh",
                device=meter_key,
                info=meter_data.info,
                power=meter_data.power.actual,
                consumption=round(meter_data.energy.totalimport / 1000, 3),
                delivery=round(meter_data.energy.totalexport / 1000, 3),
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
    ) -> Powerflow:
        """
        Calculates the power flow in the system by summing the power of all meters and batteries.
        It considers both import and export options for each meter in the calculation.
        Returns a PowerFlow object representing the total power flow in the system.
        """

        powerflow = Powerflow.calc(inverter, meters, batteries)

        logger.debug(powerflow)
        logger.info(
            "Powerflow: PV {pv_production} W, Inverter {inverter.power} W, "
            + "House {house_consumption} W, "
            + "Grid {grid.power} W, Battery {battery.power} W",
            pv_production=powerflow.pv_production,
            inverter=powerflow.inverter,
            house_consumption=powerflow.house_consumption,
            grid=powerflow.grid,
            battery=powerflow.battery,
        )

        return powerflow
