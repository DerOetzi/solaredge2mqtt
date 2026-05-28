from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.mqtt.state import ServiceStateController
from solaredge2mqtt.core.timer.events import IntervalBaseTriggerEvent
from solaredge2mqtt.services.modbus import Modbus
from solaredge2mqtt.services.modbus.exceptions import InvalidRegisterDataException
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery
from solaredge2mqtt.services.powerflow.events import PowerflowGeneratedEvent
from solaredge2mqtt.services.powerflow.models import Powerflow
from solaredge2mqtt.services.wallbox import WallboxClient
from solaredge2mqtt.services.wallbox.models import WallboxAPI

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings


class PowerflowService:
    def __init__(
        self,
        settings: ServiceSettings,
        influxdb: InfluxDBAsync | None = None,
    ):
        self.settings = settings

        self.influxdb = influxdb

        self.modbus = Modbus(self.settings)
        self.modbus_state = ServiceStateController(
            "modbus",
            self.settings.service_state.debounce_for("modbus"),
        )
        self.wallbox_state = ServiceStateController(
            "wallbox",
            self.settings.service_state.debounce_for("wallbox"),
        )

        self.wallbox = (
            WallboxClient(self.settings.wallbox)
            if self.settings.wallbox.is_configured
            else None
        )

        EventBus.register(self)

    async def async_init(self) -> None:
        try:
            await self.modbus.async_init()
            await self.modbus_state.set_online()
        except (InvalidDataException, InvalidRegisterDataException, RuntimeError):
            await self.modbus_state.set_offline()
            raise

    @EventBus.subscribe(IntervalBaseTriggerEvent)
    async def calculate_powerflow(
        self, event: IntervalBaseTriggerEvent | None = None
    ) -> None:
        try:
            units = await self.modbus.get_data()
            await self.modbus_state.set_online()
        except (InvalidDataException, RuntimeError):
            await self.modbus_state.set_offline()
            raise

        if "leader" not in units:
            raise InvalidDataException("Invalid modbus data no leader unit")

        batteries = self._check_batteries(units)

        evcharger, wallbox_data = await self._read_wallbox_data()

        powerflows = self._powerflows_from_data(units, evcharger)

        if self.settings.modbus.has_followers:
            powerflow = Powerflow.cumulated_powerflow(powerflows)
            powerflows["cumulated"] = powerflow
        else:
            powerflow = powerflows["leader"]

        if not powerflow.is_valid(self.settings.powerflow.external_production):
            logger.info(powerflow)
            raise InvalidDataException("Invalid powerflow data")

        if Powerflow.is_not_valid_with_last(powerflow):
            logger.debug(powerflow)
            raise InvalidDataException("Value change not valid, skipping this loop")

        await self.write_to_influxdb(powerflows, batteries)

        logger.debug(powerflow)
        logger.info(
            "Powerflow: PV {pv_production} W, Inverter {inverter.power} W, "
            + "House {consumer.house} W, Grid {grid.power} W, "
            + "Battery {battery.power} W, Wallbox {consumer.evcharger} W",
            pv_production=powerflow.pv_production,
            inverter=powerflow.inverter,
            consumer=powerflow.consumer,
            grid=powerflow.grid,
            battery=powerflow.battery,
        )

        await self.publish_modbus(units)

        await self.publish_wallbox(wallbox_data)

        await self.publish_powerflow(powerflows)

    def _check_batteries(self, units):
        batteries = {
            f"{unit_key}:{battery_key}": battery
            for unit_key, unit in units.items()
            for battery_key, battery in unit.batteries.items()
        }

        for battery in batteries.values():
            if not battery.is_valid:
                logger.debug(battery)
                raise InvalidDataException("Invalid battery data")
        return batteries

    async def _read_wallbox_data(self) -> tuple[int, WallboxAPI | None]:
        evcharger = 0
        wallbox_data = None
        if self.wallbox:
            try:
                wallbox_data = await self.wallbox.get_data()
                await self.wallbox_state.set_online()
                logger.trace(
                    "Wallbox: {wallbox_data.power} W", wallbox_data=wallbox_data
                )
                evcharger = wallbox_data.power
            except ConfigurationException as ex:
                await self.wallbox_state.set_offline()
                logger.warning(f"{ex.component}: {ex.message}")
            except InvalidDataException as ex:
                await self.wallbox_state.set_offline()
                logger.warning(f"Wallbox data invalid: {ex}")

        return evcharger, wallbox_data

    def _powerflows_from_data(self, units, evcharger):
        powerflows: dict[str, Powerflow] = {}

        for unit_key, unit in units.items():
            if unit_key == "leader":
                powerflows[unit_key] = Powerflow.from_modbus(unit, evcharger)
            else:
                powerflows[unit_key] = Powerflow.from_modbus(unit)

            logger.trace(powerflows[unit_key].model_dump_json())

        return powerflows

    async def publish_modbus(self, units):
        for key, unit in units.items():
            await EventBus.emit(
                MQTTPublishEvent(
                    unit.inverter.mqtt_topic(self.settings.modbus.has_followers),
                    unit.inverter,
                    self.settings.modbus.retain,
                )
            )

            for key, component in {**unit.meters, **unit.batteries}.items():
                await EventBus.emit(
                    MQTTPublishEvent(
                        f"{component.mqtt_topic(self.settings.modbus.has_followers)}/{key.lower()}",
                        component,
                        self.settings.modbus.retain,
                    )
                )

    async def publish_wallbox(self, wallbox_data):
        if wallbox_data is not None:
            await EventBus.emit(
                MQTTPublishEvent(
                    wallbox_data.mqtt_topic(),
                    wallbox_data,
                    self.settings.wallbox.retain,
                )
            )

    async def publish_powerflow(self, powerflows: dict[str, Powerflow]) -> None:
        if self.settings.modbus.has_followers:
            for pf in powerflows.values():
                await EventBus.emit(
                    MQTTPublishEvent(
                        pf.mqtt_topic(), pf, self.settings.powerflow.retain
                    )
                )
        else:
            powerflow = powerflows["leader"]
            await EventBus.emit(
                MQTTPublishEvent(
                    powerflow.mqtt_topic(), powerflow, self.settings.powerflow.retain
                )
            )

        await EventBus.emit(PowerflowGeneratedEvent(powerflows))

    async def write_to_influxdb(
        self,
        powerflows: dict[str, Powerflow],
        batteries_data: dict[str, ModbusBattery],
    ):
        if self.influxdb is not None:
            points = []

            for powerflow in powerflows.values():
                points.append(powerflow.prepare_point())

            for battery in batteries_data.values():
                points.append(battery.prepare_point())

            await self.influxdb.write_points(points)

    async def close(self) -> None:
        if self.wallbox:
            await self.wallbox_state.set_offline()
            await self.wallbox.close()
