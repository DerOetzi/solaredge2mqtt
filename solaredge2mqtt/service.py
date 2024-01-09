"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the aiomqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""
import asyncio
import datetime as dt
import signal

from scheduler.asyncio import Scheduler

from solaredge2mqtt.api import MonitoringSite
from solaredge2mqtt.logging import initialize_logging, logger
from solaredge2mqtt.modbus import Modbus
from solaredge2mqtt.models import Powerflow
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.persistence.influxdb import InfluxDB
from solaredge2mqtt.settings import service_settings
from solaredge2mqtt.wallbox import WallboxClient


def run():
    service = Service()
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, service.cancel)
    loop.add_signal_handler(signal.SIGTERM, service.cancel)
    loop.run_until_complete(service.main_loop())
    loop.close()


class Service:
    BASIC_VALUES_LOCK = "basic_values"
    MONITORING_LOCK = "monitoring"

    def __init__(self):
        self.settings = service_settings()
        self.scheduler: Scheduler

        self.modbus = Modbus(self.settings)
        self.mqtt: MQTTClient

        self.cancel_request = asyncio.Event()
        self.locks: dict[str, asyncio.Lock] = {}

        self.wallbox: WallboxClient | None = (
            WallboxClient(self.settings)
            if self.settings.is_wallbox_configured
            else None
        )

        self.influxdb: InfluxDB | None = (
            InfluxDB(self.settings) if self.settings.is_influxdb_configured else None
        )

        self.monitoring: MonitoringSite | None = (
            MonitoringSite(self.settings) if self.settings.is_api_configured else None
        )

    def cancel(self):
        logger.info("Stopping SolarEdge2MQTT service...")
        self.cancel_request.set()

    async def main_loop(self):
        initialize_logging(self.settings.logging_level)
        logger.info("Starting SolarEdge2MQTT service...")
        logger.debug(self.settings)

        logger.info("Timezone: {timezone}", timezone=self.settings.timezone)

        if self.settings.is_influxdb_configured:
            self.influxdb.initialize_buckets()
            self.influxdb.initialize_task()

        async with MQTTClient(self.settings) as self.mqtt:
            await self.mqtt.publish_status_online()

            self.scheduler = Scheduler(loop=asyncio.get_running_loop())
            self.scheduler.cyclic(
                dt.timedelta(seconds=self.settings.interval),
                self.basic_values_loop,
            )

            if self.settings.is_api_configured:
                self.monitoring.login()
                await self.monitoring_loop()
                self.scheduler.cyclic(dt.timedelta(minutes=5), self.monitoring_loop)

            if self.settings.is_influxdb_configured:
                await self.energy_loop()
                self.scheduler.cyclic(dt.timedelta(minutes=5), self.energy_loop)

            logger.debug(self.scheduler)

            while not self.cancel_request.is_set():
                await asyncio.sleep(1)

            if self.scheduler is not None:
                self.scheduler.delete_jobs()

            if self.mqtt is not None:
                await self.mqtt.publish_status_offline()

    async def basic_values_loop(self):
        if self.locks.get(self.BASIC_VALUES_LOCK) is None:
            self.locks[self.BASIC_VALUES_LOCK] = asyncio.Lock()

        if self.locks[self.BASIC_VALUES_LOCK].locked():
            logger.warning("Previous loop is still running, skipping this loop")
            return

        async with self.locks[self.BASIC_VALUES_LOCK]:
            results = await asyncio.gather(
                self.modbus.loop(),
                self.wallbox.loop()
                if self.settings.is_wallbox_configured
                else asyncio.sleep(0),
            )

            inverter_data, meters_data, batteries_data = results[0]

            if any(
                data is None for data in [inverter_data, meters_data, batteries_data]
            ):
                logger.warning("Invalid modbus data, skipping this loop")
                return

            wallbox_data = results[1]
            evcharger = 0

            if wallbox_data is not None:
                logger.trace(
                    "Wallbox: {wallbox_data.power} W", wallbox_data=wallbox_data
                )
                evcharger = wallbox_data.power
            elif self.settings.is_wallbox_configured:
                logger.warning("Invalid wallbox data, skipping this loop")
                logger.debug(wallbox_data)
                return

            powerflow = Powerflow(inverter_data, meters_data, batteries_data, evcharger)
            if not powerflow.is_valid:
                logger.warning("Invalid powerflow data, skipping this loop")
                logger.info(powerflow)
                return

            if Powerflow.is_not_valid_with_last(powerflow):
                logger.warning("Value change not valid, skipping this loop")
                logger.debug(powerflow)
                return

            logger.debug(powerflow)
            logger.info(
                "Powerflow: PV {pv_production} W, Inverter {inverter.power} W, House {consumer.house} W, "
                + "Grid {grid.power} W, Battery {battery.power} W, Wallbox {consumer.evcharger} W",
                pv_production=powerflow.pv_production,
                inverter=powerflow.inverter,
                consumer=powerflow.consumer,
                grid=powerflow.grid,
                battery=powerflow.battery,
            )

            await self.mqtt.publish_components(
                inverter_data, meters_data, batteries_data, wallbox_data
            )
            await self.mqtt.publish_powerflow(powerflow)

            if self.influxdb is not None:
                self.influxdb.write_components(
                    inverter_data, meters_data, batteries_data, wallbox_data
                )
                self.influxdb.write_powerflow(powerflow)

                self.influxdb.flush_loop()

    async def monitoring_loop(self):
        if self.locks.get(self.MONITORING_LOCK) is None:
            self.locks[self.MONITORING_LOCK] = asyncio.Lock()

        if self.locks[self.MONITORING_LOCK].locked():
            logger.warning("Monitoring is still locked, skipping this loop")
            return

        async with self.locks[self.MONITORING_LOCK]:
            modules = self.monitoring.get_module_energies()

            if modules is None:
                logger.warning("Invalid monitoring data, skipping this loop")
                return

            energy_total = 0
            count_modules = 0
            for module in modules:
                if module.energy is not None:
                    count_modules += 1
                    energy_total += module.energy

            logger.info(
                "Read from monitoring total energy: {energy_total} kWh from {count_modules} modules",
                energy_total=energy_total / 1000,
                count_modules=count_modules,
            )

            await self.mqtt.publish_pv_energy_today(energy_total)
            await self.mqtt.publish_module_energy(modules)

    async def energy_loop(self):
        pass
