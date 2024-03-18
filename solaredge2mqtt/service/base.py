from solaredge2mqtt.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import (
    HistoricEnergy,
    HistoricPeriod,
    HistoricQuery,
    Powerflow,
)
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.service.influxdb import InfluxDB
from solaredge2mqtt.service.modbus import Modbus
from solaredge2mqtt.service.wallbox import WallboxClient
from solaredge2mqtt.settings import ServiceSettings


class BaseLoops:
    def __init__(
        self,
        settings: ServiceSettings,
        mqtt: MQTTClient,
        influxdb: InfluxDB | None = None,
    ):
        self.settings = settings

        self.mqtt = mqtt

        self.influxdb = influxdb

        self.modbus = Modbus(self.settings.modbus)

        self.wallbox = (
            WallboxClient(self.settings.wallbox)
            if self.settings.is_wallbox_configured
            else None
        )

    async def powerflow_loop(self) -> None:
        inverter_data, meters_data, batteries_data = await self.modbus.loop()

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
                wallbox_data = await self.wallbox.loop()
                logger.trace(
                    "Wallbox: {wallbox_data.power} W", wallbox_data=wallbox_data
                )
                evcharger = wallbox_data.power
            except ConfigurationException as ex:
                logger.warning(f"{ex.component}: {ex.message}")

        powerflow = Powerflow(inverter_data, meters_data, batteries_data, evcharger)
        if not powerflow.is_valid:
            logger.info(powerflow)
            raise InvalidDataException("Invalid powerflow data")

        if Powerflow.is_not_valid_with_last(powerflow):
            logger.debug(powerflow)
            raise InvalidDataException("Value change not valid, skipping this loop")

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

        await self.mqtt.publish_to(inverter_data.mqtt_topic, inverter_data)
        for key, component in {**meters_data, **batteries_data}.items():
            await self.mqtt.publish_to(
                f"{component.mqtt_topic}/{key.lower()}", component
            )

        if wallbox_data is not None:
            await self.mqtt.publish_to(wallbox_data.mqtt_topic, wallbox_data)

        await self.mqtt.publish_to("powerflow", powerflow)

        if self.influxdb is not None:
            points = [powerflow.prepare_point()]

            for battery in batteries_data.values():
                points.append(battery.prepare_point())

            self.influxdb.write_points(points)

    async def energy_loop(self):
        for period in HistoricPeriod:
            record = self.influxdb.query_timeunit(period, "energy")
            if record is None:
                if period.query == HistoricQuery.LAST:
                    logger.info(
                        "No data found for {period}, skipping this loop", period=period
                    )
                else:
                    raise InvalidDataException(f"No energy data for {period}")

                continue

            energy = HistoricEnergy(record, period)

            logger.info(
                "Read from influxdb {period} energy: {energy.pv_production} kWh",
                period=period,
                energy=energy,
            )

            await self.mqtt.publish_to(f"energy/{period.topic}", energy)
