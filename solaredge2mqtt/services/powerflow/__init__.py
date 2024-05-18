from __future__ import annotations
from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDB
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import IntervalBaseTriggerEvent
from solaredge2mqtt.services.modbus import Modbus
from solaredge2mqtt.services.modbus.models import SunSpecBattery
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
        influxdb: InfluxDB | None = None,
    ):
        self.settings = settings

        self.influxdb = influxdb

        self.modbus = Modbus(self.settings.modbus, event_bus)

        self.wallbox = (
            WallboxClient(self.settings.wallbox, event_bus)
            if self.settings.is_wallbox_configured
            else None
        )

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(IntervalBaseTriggerEvent, self.calculate_powerflow)

    async def calculate_powerflow(self, _) -> None:
        inverter_data, meters_data, batteries_data = await self.modbus.get_data()

        if any(data is None for data in [inverter_data, meters_data, batteries_data]):
            raise InvalidDataException("Invalid modbus data")

        for battery in batteries_data.values():
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

        powerflow = Powerflow.from_modbus(
            inverter_data, meters_data, batteries_data, evcharger
        )
        if not powerflow.is_valid:
            logger.info(powerflow)
            raise InvalidDataException("Invalid powerflow data")

        if Powerflow.is_not_valid_with_last(powerflow):
            logger.debug(powerflow)
            raise InvalidDataException("Value change not valid, skipping this loop")

        self.write_to_influxdb(batteries_data, powerflow)

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

        await self.event_bus.emit(
            MQTTPublishEvent(inverter_data.mqtt_topic(), inverter_data)
        )

        for key, component in {**meters_data, **batteries_data}.items():
            await self.event_bus.emit(
                MQTTPublishEvent(
                    f"{component.mqtt_topic()}/{key.lower()}",
                    component,
                )
            )

        if wallbox_data is not None:
            await self.event_bus.emit(
                MQTTPublishEvent(wallbox_data.mqtt_topic(), wallbox_data)
            )

        await self.event_bus.emit(MQTTPublishEvent(powerflow.mqtt_topic(), powerflow))

        await self.event_bus.emit(PowerflowGeneratedEvent(powerflow))

    def write_to_influxdb(
        self, batteries_data: dict[str, SunSpecBattery], powerflow: Powerflow
    ):
        if self.influxdb is not None:
            points = [powerflow.prepare_point()]

            for battery in batteries_data.values():
                points.append(battery.prepare_point())

            self.influxdb.write_points(points)
