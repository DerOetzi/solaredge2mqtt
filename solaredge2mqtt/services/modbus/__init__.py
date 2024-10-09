from datetime import datetime, timedelta
import json

from pymodbus.client import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.exceptions import ModbusException
from pymodbus.payload import BinaryPayloadDecoder

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
from solaredge2mqtt.services.modbus.sunspec import (
    SunSpecBatteryOffset,
    SunSpecBatteryRegister,
    SunSpecInverterRegister,
    SunSpecMeterOffset,
    SunSpecMeterRegister,
    SunSpecPayload,
    SunSpecRegister,
    SunSpecRegisterSlice,
)


LOGGING_DEVICE_INFO = "{device} ({info.manufacturer} {info.model} {info.serialnumber})"


class Modbus:

    def __init__(self, settings: ModbusSettings, event_bus: EventBus):
        self.settings = settings
        self.client = ModbusTcpClient(
            host=settings.host, port=settings.port, timeout=settings.timeout
        )

        logger.info(
            "Using SolarEdge inverter via modbus: {host}:{port}",
            host=settings.host,
            port=settings.port,
        )

        self.event_bus = event_bus

        self._block_unreadable: dict[SunSpecRegisterSlice, datetime] = {}

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
        except KeyError as error:
            raise InvalidDataException("Invalid modbus data") from error

        await self.event_bus.emit(ModbusInverterReadEvent(inverter_data))
        if meters_data:
            await self.event_bus.emit(ModbusMetersReadEvent(meters_data))
        if batteries_data:
            await self.event_bus.emit(ModbusBatteriesReadEvent(batteries_data))

        return inverter_data, meters_data, batteries_data

    def _get_raw_data(
        self,
    ) -> tuple[SunSpecPayload, dict[str, SunSpecPayload], dict[str, SunSpecPayload]]:
        inverter_raw = self._read_from_modbus(SunSpecInverterRegister)
        meters_raw = {}

        for meter in SunSpecMeterOffset:
            if meter.identifier in inverter_raw and inverter_raw[meter.identifier] > 0:
                meters_raw[meter.identifier] = self._read_from_modbus(
                    SunSpecMeterRegister, offset=meter.offset
                )

        batteries_raw = {}
        for battery in SunSpecBatteryOffset:
            if (
                battery.identifier in inverter_raw
                and inverter_raw[battery.identifier] != 255
            ):
                logger.debug(
                    f"Read battery {battery} with deviceaddress {inverter_raw[battery.identifier]}"
                )
                batteries_raw[battery.identifier] = self._read_from_modbus(
                    SunSpecBatteryRegister, offset=battery.offset
                )

        return inverter_raw, meters_raw, batteries_raw

    def _read_from_modbus(
        self, registers: SunSpecRegister, offset: int = 0
    ) -> SunSpecPayload:
        data = {}

        for register_slice in registers.registers_sliced():

            slice_start = register_slice.registers_start_address() + offset

            if register_slice in self._block_unreadable:
                if datetime.now() - self._block_unreadable[register_slice] < timedelta(
                    minutes=2
                ):
                    logger.debug(
                        f"Skip unreadable registers beginning at {slice_start}"
                    )
                    continue

                del self._block_unreadable[register_slice]
                logger.info(f"Retry unreadable registers beginning at {slice_start}")

            logger.trace(
                f"Read {register_slice.registers_length()} registers beginning at {slice_start}"
            )

            try:
                result = self.client.read_holding_registers(
                    slave=self.settings.unit,
                    address=slice_start,
                    count=register_slice.registers_length(),
                )

                if result.isError():
                    logger.trace(f"Modbus read error: {result}")
                    self._block_register_slice(register_slice, offset)
                else:
                    decoder = BinaryPayloadDecoder.fromRegisters(
                        result.registers,
                        byteorder=Endian.BIG,
                        wordorder=registers.wordorder(),
                    )

                    data = register_slice.payload_decode(decoder, data)
            except ModbusException as error:
                logger.trace(f"Modbus read exception: {error}")

        return data

    def _block_register_slice(
        self, register_slice: SunSpecRegisterSlice, offset: int
    ) -> None:
        logger.info(
            f"Block unreadable registers beginning at {register_slice.registers_start_address() + offset}"
        )
        self._block_unreadable[register_slice] = datetime.now()

    def _map_inverter(self, inverter_raw: SunSpecPayload) -> SunSpecInverter:
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
        self, meters_raw: dict[str, SunSpecPayload]
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
        self, batteries_raw: dict[str, SunSpecPayload]
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
                LOGGING_DEVICE_INFO + ": {status}, {power} W, {state_of_charge} %",
                device=battery_key,
                info=battery_data.info,
                status=battery_data.status,
                power=battery_data.power,
                state_of_charge=battery_data.state_of_charge,
            )

            batteries[battery_key] = battery_data

        return batteries
