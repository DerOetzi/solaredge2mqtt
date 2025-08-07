from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.modbus.control import ModbusAdvancedControl
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent, ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.base import ModbusDeviceInfo
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.models.meter import ModbusMeter
from solaredge2mqtt.services.modbus.models.unit import ModbusUnit
from solaredge2mqtt.services.modbus.settings import ModbusUnitSettings
from solaredge2mqtt.services.modbus.sunspec.base import (
    SunSpecRegister,
    SunSpecRequestRegisterBundle,
)
from solaredge2mqtt.services.modbus.sunspec.battery import (
    SunSpecBatteryInfoRegister,
    SunSpecBatteryOffset,
    SunSpecBatteryRegister,
)
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecGridStatusRegister,
    SunSpecInverterInfoRegister,
    SunSpecInverterRegister,
    SunSpecPowerControlRegister,
)
from solaredge2mqtt.services.modbus.sunspec.meter import (
    SunSpecMeterInfoRegister,
    SunSpecMeterOffset,
    SunSpecMeterRegister,
)
from solaredge2mqtt.services.modbus.sunspec.values import (
    SunSpecInputData,
    SunSpecPayload,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings

LOGGING_DEVICE_INFO = (
    "{unit_key}{device} ({info.manufacturer} {info.model} {info.serialnumber})"
)


class Modbus:
    def __init__(self, settings: ServiceSettings, event_bus: EventBus):
        self.settings = settings.modbus

        logger.info(
            "Using SolarEdge inverter via modbus: {host}:{port}",
            host=self.settings.host,
            port=self.settings.port,
        )

        logger.debug(f"Modbus settings: {self.settings}")

        self.event_bus = event_bus

        self._block_unreadable: set[int] = set()

        self._initialized = False
        self._device_info: dict[str, dict[str, ModbusDeviceInfo]] = {}

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
            for unit_key, unit_settings in self.settings.units.items():
                logger.info(f"Detecting devices for unit: {unit_key}")

                self._device_info[unit_key] = {}

                inverter_raw = await self.read_device_info(
                    SunSpecInverterInfoRegister, unit_key, "inverter", unit_settings
                )

                logger.debug(f"Detected inverter: {inverter_raw}")

                for meter in SunSpecMeterOffset:
                    if (
                        unit_settings.meter[meter.idx]
                        and meter.identifier in inverter_raw
                        and inverter_raw[meter.identifier] > 0
                    ):
                        await self.read_device_info(
                            SunSpecMeterInfoRegister,
                            unit_key,
                            meter.identifier,
                            unit_settings,
                            meter.offset,
                        )

                for battery in SunSpecBatteryOffset:
                    if (
                        unit_settings.battery[battery.idx]
                        and battery.identifier in inverter_raw
                        and inverter_raw[battery.identifier] != 255
                    ):
                        await self.read_device_info(
                            SunSpecBatteryInfoRegister,
                            unit_key,
                            battery.identifier,
                            unit_settings,
                            battery.offset,
                        )

    async def read_device_info(
        self,
        registers: SunSpecRegister,
        unit_key: str,
        key: str,
        unit_settings: ModbusUnitSettings,
        offset: int = 0
    ) -> SunSpecPayload:
        raw_data = await self._read_from_modbus(registers,
                                                unit_settings.unit,
                                                offset)

        if self.settings.has_followers:
            raw_data["unit"] = {
                "unit": unit_settings.unit,
                "key": unit_key,
                "role": unit_settings.role
            }

        info = ModbusDeviceInfo(raw_data)
        logger.info(
            f"Found {key} {info.manufacturer} {info.model} {info.serialnumber}")
        self._device_info[unit_key][key] = info
        return raw_data

    async def check_readable_registers(self):
        self.client = AsyncModbusTcpClient(
            host=self.settings.host,
            port=self.settings.port,
            timeout=self.settings.timeout,
            retries=1,
        )

        async with self.client:
            for unit_key, unit_settings in self.settings.units.items():
                logger.info(
                    f"Checking modbus registers from unit: {unit_key}",)
                await self._get_raw_data(unit_key, unit_settings.unit)

    async def get_data(
        self,
    ) -> ModbusUnit:
        units: dict[str, ModbusUnit] = {}

        try:
            async with self.client:
                for unit_key, unit_settings in self.settings.units.items():
                    inverter_raw, meters_raw, batteries_raw = await self._get_raw_data(
                        unit_key, unit_settings.unit
                    )

                    inverter_data = self._map_inverter(unit_key, inverter_raw)
                    meters_data = self._map_meters(unit_key, meters_raw)
                    batteries_data = self._map_batteries(unit_key, batteries_raw)
    
                    units[unit_key] = ModbusUnit(
                        info=inverter_data.info.unit,
                        inverter=inverter_data,
                        meters=meters_data,
                        batteries=batteries_data
                    )

        except KeyError as error:
            raise InvalidDataException("Invalid modbus data") from error

        await self.event_bus.emit(ModbusUnitsReadEvent(units))

        return units

    async def _get_raw_data(
        self,
        unit_key: str,
        unit: int
    ) -> tuple[SunSpecPayload, dict[str, SunSpecPayload], dict[str, SunSpecPayload]]:

        inverter_raw = await self._read_from_modbus(
            SunSpecInverterRegister.request_bundles(),
            unit,
        )

        if self.settings.check_grid_status:
            grid_status_raw = await self._read_from_modbus(
                SunSpecGridStatusRegister.request_bundles(),
                unit,
            )
            inverter_raw = {**inverter_raw, **grid_status_raw}

        if self.settings.advanced_power_controls_enabled:
            advanced_power_control_raw = await self._read_from_modbus(
                SunSpecPowerControlRegister.request_bundles(),
                unit,
            )
            inverter_raw = {
                **inverter_raw,
                **advanced_power_control_raw,
            }

            logger.debug(advanced_power_control_raw)

        meters_raw = {}
        batteries_raw = {}

        for meter in SunSpecMeterOffset:
            if meter.identifier in self._device_info[unit_key]:
                meters_raw[meter.identifier] = await self._read_from_modbus(
                    SunSpecMeterRegister.request_bundles(),
                    unit,
                    offset=meter.offset
                )

        for battery in SunSpecBatteryOffset:
            if battery.identifier in self._device_info[unit_key]:
                batteries_raw[battery.identifier] = await self._read_from_modbus(
                    SunSpecBatteryRegister.request_bundles(),
                    unit,
                    offset=battery.offset
                )

        return inverter_raw, meters_raw, batteries_raw

    async def _read_from_modbus(
        self,
        registers_or_bundles: SunSpecRegister | list[SunSpecRequestRegisterBundle],
        unit: int,
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
                (
                    f"Read {register_or_bundle.length} register "
                    f"beginning at {address_start}"
                )
            )

            try:
                result = await self.client.read_holding_registers(
                    device_id=unit,
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

                if not self._initialized:
                    logger.trace(
                        (
                            f"Checked {register_or_bundle.length} registers "
                            f"from {address_start} successfully"
                        )
                    )

            except ModbusException as error:
                logger.debug(f"Modbus read exception: {error}")
                logger.error(f"Unreadable register {address_start}")
                self._block_register(address_start)

        return data

    def _block_register(self, register: int) -> None:
        if not self._initialized:
            logger.info(f"Block unreadable register beginning at {register}")
            self._block_unreadable.add(register)

    def _map_inverter(
        self, unit_key: str, inverter_raw: SunSpecPayload
    ) -> ModbusInverter:
        logger.debug(
            "Inverter raw:\n{raw}",
            raw=json.dumps(inverter_raw, indent=4),
        )

        inverter_data = ModbusInverter(
            self._device_info[unit_key]["inverter"], inverter_raw)
        logger.debug(inverter_data)

        logger.info(
            LOGGING_DEVICE_INFO
            + ": {status}, AC {power_ac} W, DC {power_dc} W, {energytotal} kWh, "
            + "Grid status {grid_status}, ",
            unit_key=inverter_data.info.unit_key(":"),
            device="inverter",
            info=inverter_data.info,
            status=inverter_data.status,
            power_ac=inverter_data.ac.power.actual,
            power_dc=inverter_data.dc.power,
            energytotal=round(inverter_data.energytotal / 1000, 2),
            grid_status=inverter_data.grid_status,
        )

        return inverter_data

    def _map_meters(
        self, unit_key: str, meters_raw: dict[str, SunSpecPayload]
    ) -> dict[str, ModbusMeter]:
        meters: dict[str, ModbusMeter] = {}
        for meter_key, meter_raw in meters_raw.items():
            logger.debug(
                "Meter {meter} raw:\n{raw}",
                meter=meter_key,
                raw=json.dumps(meter_raw, indent=4),
            )

            meter_data = ModbusMeter(
                self._device_info[unit_key][meter_key], meter_raw)
            logger.debug(meter_data)
            logger.info(
                LOGGING_DEVICE_INFO +
                ": {power} W, {consumption} kWh, {delivery} kWh",
                unit_key=meter_data.info.unit_key(":"),
                device=meter_key,
                info=meter_data.info,
                power=meter_data.power.actual,
                consumption=round(meter_data.energy.totalimport / 1000, 3),
                delivery=round(meter_data.energy.totalexport / 1000, 3),
            )

            meters[meter_key] = meter_data

        return meters

    def _map_batteries(
        self, unit_key: str, batteries_raw: dict[str, SunSpecPayload]
    ) -> dict[str, ModbusBattery]:
        batteries = {}
        for battery_key, battery_raw in batteries_raw.items():
            logger.debug(
                "Battery {battery} raw:\n{raw}",
                battery=battery_key,
                raw=json.dumps(battery_raw, indent=4),
            )

            battery_data = ModbusBattery(
                self._device_info[unit_key][battery_key], battery_raw)
            logger.debug(battery_data)
            logger.info(
                LOGGING_DEVICE_INFO +
                ": {status}, {power} W, {state_of_charge} %",
                unit_key=battery_data.info.unit_key(":"),
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

    async def _write_to_modbus(
        self, register: SunSpecRegister, value: SunSpecInputData
    ) -> None:
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
                    device_id=self.settings.unit,
                )

        except ModbusException as error:
            logger.debug(f"Modbus write exception: {error}")
            logger.error(f"Unwriteable register {register.address}")
