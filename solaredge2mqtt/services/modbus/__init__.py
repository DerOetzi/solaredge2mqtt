from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from annotated_types import T
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.modbus.control import ModbusAdvancedControl
from solaredge2mqtt.services.modbus.events import (ModbusBatteriesReadEvent,
                                                   ModbusInverterReadEvent,
                                                   ModbusMetersReadEvent,
                                                   ModbusWriteEvent)
from solaredge2mqtt.services.modbus.models.base import ModbusDeviceInfo
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.models.meter import ModbusMeter
from solaredge2mqtt.services.modbus.sunspec.base import (
    SunSpecRegister, SunSpecRequestRegisterBundle)
from solaredge2mqtt.services.modbus.sunspec.battery import (
    SunSpecBatteryInfoRegister, SunSpecBatteryOffset, SunSpecBatteryRegister)
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecGridStatusRegister, SunSpecInverterInfoRegister,
    SunSpecInverterRegister, SunSpecPowerControlRegister)
from solaredge2mqtt.services.modbus.sunspec.meter import (
    SunSpecMeterInfoRegister, SunSpecMeterOffset, SunSpecMeterRegister)
from solaredge2mqtt.services.modbus.sunspec.values import (SunSpecInputData,
                                                           SunSpecPayload)

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings

LOGGING_DEVICE_INFO = "{device} ({info.manufacturer} {info.model} {info.serialnumber})"


class Modbus:
    def __init__(self, settings: ServiceSettings, event_bus: EventBus):
        self.settings = settings.modbus

        logger.info(
            "Using SolarEdge inverter via modbus: {host}:{port}",
            host=self.settings.host,
            port=self.settings.port,
        )

        self.event_bus = event_bus

        self._block_unreadable: set[int] = set()

        self._initialized = False
        self._device_info: dict[str, ModbusDeviceInfo] = {}

        self.client: AsyncModbusTcpClient | None = None

        self._control: ModbusAdvancedControl = ModbusAdvancedControl(
            settings, event_bus)

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(ModbusWriteEvent, self._handle_write_event)

    async def async_init(self) -> None:
        logger.info("Initializing modbus")

        self.client = AsyncModbusTcpClient(
            host=self.settings.host,
            port=self.settings.port,
            timeout=self.settings.timeout,
            retries=0,
        )

        await self.detect_devices()

        await asyncio.sleep(self.settings.timeout + 5)

        await self.check_readable_registers()

        self._initialized = True

        await asyncio.sleep(self.settings.timeout + 5)
        if self._block_unreadable:
            logger.warning(
                "Not readable registers: {registers}", registers=self._block_unreadable
            )

        # await self._control.async_init()

    async def detect_devices(self):
        async with self.client:
            inverter_raw = await self.read_device_info(
                SunSpecInverterInfoRegister, "inverter"
            )

            for meter in SunSpecMeterOffset:
                if (
                    meter.identifier in inverter_raw
                    and inverter_raw[meter.identifier] > 0
                ):
                    await self.read_device_info(
                        SunSpecMeterInfoRegister, meter.identifier, meter.offset
                    )

            for battery in SunSpecBatteryOffset:
                if (
                    battery.identifier in inverter_raw
                    and inverter_raw[battery.identifier] != 255
                ):
                    await self.read_device_info(
                        SunSpecBatteryInfoRegister, battery.identifier, battery.offset
                    )

    async def read_device_info(
        self, registers: SunSpecRegister, key: str, offset: int = 0
    ) -> SunSpecPayload:
        raw_data = await self._read_from_modbus(registers, offset)
        info = ModbusDeviceInfo(raw_data)
        logger.info(
            f"Found {key} {info.manufacturer} {info.model} {info.serialnumber}")
        self._device_info[key] = info
        return raw_data

    async def check_readable_registers(self):
        self.client = AsyncModbusTcpClient(
            host=self.settings.host,
            port=self.settings.port,
            timeout=self.settings.timeout,
            retries=1,
        )

        async with self.client:
            logger.info("Reading modbus registers")
            await self._get_raw_data()

    async def get_data(
        self,
    ) -> (
        tuple[
            ModbusInverter | None,
            dict[str, ModbusMeter] | None,
            dict[str, ModbusBattery | None],
        ]
        | None
    ):
        inverter_data = None
        meters_data = None
        batteries_data = None

        try:
            inverter_raw, meters_raw, batteries_raw = await self._get_raw_data()

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

    async def _get_raw_data(
        self,
    ) -> tuple[SunSpecPayload, dict[str, SunSpecPayload], dict[str, SunSpecPayload]]:

        async with self.client:
            inverter_raw = await self._read_from_modbus(
                SunSpecInverterRegister.request_bundles()
            )

            if self.settings.check_grid_status:
                grid_status_raw = await self._read_from_modbus(
                    SunSpecGridStatusRegister.request_bundles()
                )
                inverter_raw = {**inverter_raw, **grid_status_raw}

            if self.settings.advanced_power_controls_enabled:
                advanced_power_control_raw = await self._read_from_modbus(
                    SunSpecPowerControlRegister.request_bundles()
                )
                inverter_raw = {
                    **inverter_raw,
                    **advanced_power_control_raw,
                }

                logger.debug(advanced_power_control_raw)

            meters_raw = {}
            batteries_raw = {}

            for meter in SunSpecMeterOffset:
                if meter.identifier in self._device_info:
                    meters_raw[meter.identifier] = await self._read_from_modbus(
                        SunSpecMeterRegister.request_bundles(), offset=meter.offset
                    )

            for battery in SunSpecBatteryOffset:
                if battery.identifier in self._device_info:
                    batteries_raw[battery.identifier] = await self._read_from_modbus(
                        SunSpecBatteryRegister.request_bundles(), offset=battery.offset
                    )

        return inverter_raw, meters_raw, batteries_raw

    async def _read_from_modbus(
        self,
        registers_or_bundles: SunSpecRegister | list[SunSpecRequestRegisterBundle],
        offset: int = 0,
    ) -> SunSpecPayload:
        data = {}

        for register_or_bundle in registers_or_bundles:
            address_start = register_or_bundle.address + offset

            if address_start in self._block_unreadable:
                logger.trace(
                    f"Skip unreadable registers beginning at {address_start}")
                continue

            logger.trace(
                f"Read {register_or_bundle.length} register beginning at {address_start}"
            )

            try:
                result = await self.client.read_holding_registers(
                    slave=self.settings.unit,
                    address=address_start,
                    count=register_or_bundle.length,
                )

                if result.isError():
                    logger.error(f"Unreadable register {address_start}")
                    logger.debug(f"Modbus read error: {result}")
                    self._block_register(address_start)
                else:
                    data = register_or_bundle.decode_response(
                        result.registers, data)

            except ModbusException as error:
                logger.debug(f"Modbus read exception: {error}")
                logger.error(f"Unreadable register {address_start}")
                self._block_register(address_start)

        return data

    def _block_register(self, register: int) -> None:
        if not self._initialized:
            logger.info(f"Block unreadable register beginning at {register}")
            self._block_unreadable.add(register)

    def _map_inverter(self, inverter_raw: SunSpecPayload) -> ModbusInverter:
        logger.debug(
            "Inverter raw:\n{raw}",
            raw=json.dumps(inverter_raw, indent=4),
        )

        inverter_data = ModbusInverter(
            self._device_info["inverter"], inverter_raw)
        logger.debug(inverter_data)

        logger.info(
            LOGGING_DEVICE_INFO
            + ": {status}, AC {power_ac} W, DC {power_dc} W, {energytotal} kWh, "
            + "Grid status {grid_status}, ",
            device="Inverter",
            info=inverter_data.info,
            status=inverter_data.status,
            power_ac=inverter_data.ac.power.actual,
            power_dc=inverter_data.dc.power,
            energytotal=round(inverter_data.energytotal / 1000, 2),
            grid_status=inverter_data.grid_status,
        )

        return inverter_data

    def _map_meters(
        self, meters_raw: dict[str, SunSpecPayload]
    ) -> dict[str, ModbusMeter]:
        meters = {}
        for meter_key, meter_raw in meters_raw.items():
            logger.debug(
                "Meter {meter} raw:\n{raw}",
                meter=meter_key,
                raw=json.dumps(meter_raw, indent=4),
            )

            meter_data = ModbusMeter(self._device_info[meter_key], meter_raw)
            logger.debug(meter_data)
            logger.info(
                LOGGING_DEVICE_INFO +
                ": {power} W, {consumption} kWh, {delivery} kWh",
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
    ) -> dict[str, ModbusBattery]:
        batteries = {}
        for battery_key, battery_raw in batteries_raw.items():
            logger.debug(
                "Battery {battery} raw:\n{raw}",
                battery=battery_key,
                raw=json.dumps(battery_raw, indent=4),
            )

            battery_data = ModbusBattery(
                self._device_info[battery_key], battery_raw)
            logger.debug(battery_data)
            logger.info(
                LOGGING_DEVICE_INFO +
                ": {status}, {power} W, {state_of_charge} %",
                device=battery_key,
                info=battery_data.info,
                status=battery_data.status,
                power=battery_data.power,
                state_of_charge=battery_data.state_of_charge,
            )

            batteries[battery_key] = battery_data

        return batteries

    async def _handle_write_event(self, event: ModbusWriteEvent):
        await self._write_to_modbus(event.register, event.payload)

    async def _write_to_modbus(self, register: SunSpecRegister, value: SunSpecInputData) -> None:
        logger.info(
            f"Writing {value} to register {register.address} ({register.name})"
        )

        value_decoded = register.encode_request(value)
        logger.trace(f"Encoded value: {value_decoded}")

        try:
            async with self.client:
                await self.client.write_registers(
                    register.address,
                    value_decoded,
                    slave=self.settings.unit,
                )

        except ModbusException as error:
            logger.debug(f"Modbus write exception: {error}")
            logger.error(f"Unwriteable register {register.address}")
