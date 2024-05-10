import json

from pymodbus.exceptions import ModbusException
from solaredge_modbus import Inverter

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.modbus.events import (
    ModbusBatteriesReadEvent,
    ModbusInverterReadEvent,
    ModbusMetersReadEvent,
)
from solaredge2mqtt.services.modbus.models import (
    SunSpecBattery,
    SunSpecInverter,
    SunSpecMeter,
)
from solaredge2mqtt.services.modbus.settings import ModbusSettings

SunSpecRawData = dict[str, str | int]

LOGGING_DEVICE_INFO = "{device} ({info.manufacturer} {info.model} {info.serialnumber})"


class Modbus:
    inverter: Inverter

    def __init__(self, settings: ModbusSettings, event_bus: EventBus):
        self.inverter = Inverter(
            host=settings.host,
            port=settings.port,
            timeout=settings.timeout,
            unit=settings.unit,
        )

        logger.info(
            "Using SolarEdge inverter via modbus: {host}:{port}",
            host=settings.host,
            port=settings.port,
        )

        self.event_bus = event_bus

    async def get_data(
        self,
    ) -> (
        tuple[
            SunSpecInverter | None,
            dict[str, SunSpecMeter] | None,
            dict[str, SunSpecBattery | None],
        ]
        | None
    ):
        inverter_data = None
        meters_data = None
        batteries_data = None

        try:
            inverter_raw, meters_raw, batteries_raw = self._get_raw_data()

            inverter_data = self._map_inverter(inverter_raw)
            meters_data = self._map_meters(meters_raw)
            batteries_data = self._map_batteries(batteries_raw)
        except (ModbusException, KeyError) as error:
            raise InvalidDataException("Invalid modbus data") from error

        await self.event_bus.emit(ModbusInverterReadEvent(inverter_data))
        if meters_data:
            await self.event_bus.emit(ModbusMetersReadEvent(meters_data))
        if batteries_data:
            await self.event_bus.emit(ModbusBatteriesReadEvent(batteries_data))

        return inverter_data, meters_data, batteries_data

    def _get_raw_data(
        self,
    ) -> tuple[SunSpecRawData, dict[str, SunSpecRawData], dict[str, SunSpecRawData]]:
        inverter_raw = self.inverter.read_all()
        meters_raw = {
            meter_key: meter_obj.read_all()
            for meter_key, meter_obj in self.inverter.meters().items()
        }
        batteries_raw = {
            battery_key: battery_raw
            for battery_key, battery_obj in self.inverter.batteries().items()
            if (battery_raw := battery_obj.read_all())
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
        self, meters_raw: dict[str, SunSpecRawData]
    ) -> dict[str, SunSpecInverter]:
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
        self, batteries_raw: dict[str, SunSpecRawData]
    ) -> dict[str, SunSpecInverter]:
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
