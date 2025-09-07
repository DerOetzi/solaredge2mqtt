from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import IntervalBaseTriggerEvent
from solaredge2mqtt.services.modbus import Modbus
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery
from solaredge2mqtt.services.powerflow.events import PowerflowGeneratedEvent
from solaredge2mqtt.services.powerflow.models import Powerflow
from solaredge2mqtt.services.wallbox import WallboxClient

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings


class PowerflowService:

    def __init__(
        self,
        settings: ServiceSettings,
        event_bus: EventBus,
        influxdb: InfluxDBAsync | None = None,
    ):
        self.settings = settings

        self.influxdb = influxdb

        self.modbus = Modbus(self.settings, event_bus)

        self.wallbox = (
            WallboxClient(self.settings.wallbox, event_bus)
            if self.settings.is_wallbox_configured
            else None
        )

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(
            IntervalBaseTriggerEvent, self.calculate_powerflow)

    async def async_init(self) -> None:
        await self.modbus.async_init()

    async def calculate_powerflow(self, _) -> None:
        units = await self.modbus.get_data()

        if "leader" not in units:
            raise InvalidDataException("Invalid modbus data")

        batteries = {
            f"{unit_key}:{battery_key}": battery
            for unit_key, unit in units.items()
            for battery_key, battery in unit.batteries.items()
        }

        for battery in batteries.values():
            if not battery.is_valid:
                logger.debug(battery)
                raise InvalidDataException("Invalid battery data")

        evcharger = 0
        wallbox_data = None
        if self.settings.is_wallbox_configured:
            try:
                wallbox_data = await self.wallbox.get_data()
                logger.trace(
                    "Wallbox: {wallbox_data.power} W", wallbox_data=wallbox_data
                )
                evcharger = wallbox_data.power
            except ConfigurationException as ex:
                logger.warning(f"{ex.component}: {ex.message}")

        powerflows: dict[str, Powerflow] = {}

        for unit_key, unit in units.items():
            if unit_key == "leader":
                powerflows[unit_key] = Powerflow.from_modbus(unit, evcharger)
            else:
                powerflows[unit_key] = Powerflow.from_modbus(unit)

            logger.trace(powerflows[unit_key].model_dump_json())

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
            raise InvalidDataException(
                "Value change not valid, skipping this loop")

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

    async def publish_modbus(self, units):
        for key, unit in units.items():
            await self.event_bus.emit(
                MQTTPublishEvent(
                    unit.inverter.mqtt_topic(
                        self.settings.modbus.has_followers),
                    unit.inverter,
                    self.settings.modbus.retain)
            )

            for key, component in {**unit.meters, **unit.batteries}.items():
                await self.event_bus.emit(
                    MQTTPublishEvent(
                        f"{component.mqtt_topic(self.settings.modbus.has_followers)}/{key.lower()}",
                        component,
                        self.settings.modbus.retain
                    )
                )

    async def publish_wallbox(self, wallbox_data):
        if wallbox_data is not None:
            await self.event_bus.emit(
                MQTTPublishEvent(
                    wallbox_data.mqtt_topic(),
                    wallbox_data,
                    self.settings.wallbox.retain
                )
            )

    async def publish_powerflow(self, powerflows: dict[str, Powerflow]) -> None:
        if self.settings.modbus.has_followers:
            for pf in powerflows.values():
                await self.event_bus.emit(
                    MQTTPublishEvent(
                        pf.mqtt_topic(),
                        pf,
                        self.settings.powerflow.retain
                    )
                )
        else:
            powerflow = powerflows["leader"]
            await self.event_bus.emit(
                MQTTPublishEvent(
                    powerflow.mqtt_topic(),
                    powerflow,
                    self.settings.powerflow.retain
                )
            )

        await self.event_bus.emit(PowerflowGeneratedEvent(powerflows))

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
        if self.settings.is_wallbox_configured:
            await self.wallbox.close()
