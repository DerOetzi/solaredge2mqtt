"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the aiomqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""

import asyncio as aio
import platform
import signal
from time import time
from typing import Callable

from aiomqtt import MqttError
from tzlocal import get_localzone_name

from solaredge2mqtt import __version__
from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.influxdb import InfluxDB
from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.mqtt import MQTTClient
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.core.timer import Timer
from solaredge2mqtt.services.energy import EnergyService
from solaredge2mqtt.services.forecast import ForecastService
from solaredge2mqtt.services.homeassistant import HomeAssistantDiscovery
from solaredge2mqtt.services.monitoring import MonitoringSite
from solaredge2mqtt.services.powerflow import PowerflowService
from solaredge2mqtt.services.weather import WeatherClient

LOCAL_TZ = get_localzone_name()


def run():
    try:
        service = Service()
        loop = aio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, service.cancel)
        loop.add_signal_handler(signal.SIGTERM, service.cancel)
        loop.run_until_complete(service.main_loop())
    except ConfigurationException:
        logger.error("Configuration error")
    except aio.exceptions.CancelledError:
        logger.debug("Service cancelled")
    finally:
        loop.close()


class Service:
    def __init__(self):
        self.settings = service_settings()
        initialize_logging(self.settings.logging_level)
        logger.debug(self.settings)

        self.event_bus = EventBus()
        self.timer = Timer(self.event_bus, self.settings.interval)

        self.mqtt: MQTTClient | None = None

        self.cancel_request = aio.Event()
        self.loops: set[aio.Task] = set()

        self.influxdb: InfluxDB | None = (
            InfluxDB(self.settings.influxdb, self.settings.prices, self.event_bus)
            if self.settings.is_influxdb_configured
            else None
        )

        self.energy: EnergyService | None = (
            EnergyService(self.event_bus, self.influxdb)
            if self.settings.is_influxdb_configured
            else None
        )

        self.powerflow = PowerflowService(self.settings, self.event_bus, self.influxdb)

        self.monitoring: MonitoringSite | None = (
            MonitoringSite(self.settings.monitoring, self.event_bus)
            if self.settings.is_monitoring_configured
            else None
        )

        self.weather: WeatherClient | None = (
            WeatherClient(self.settings, self.event_bus)
            if self.settings.is_weather_configured
            else None
        )

        self.forecast: ForecastService | None = (
            ForecastService(
                self.settings.forecast,
                self.settings.location,
                self.event_bus,
                self.influxdb,
            )
            if self.settings.is_forecast_configured
            else None
        )

        self.homeassistant: HomeAssistantDiscovery | None = (
            HomeAssistantDiscovery(self.settings, self.event_bus)
            if self.settings.is_homeassistant_configured
            else None
        )

    def cancel(self):
        logger.info("Stopping SolarEdge2MQTT service...")
        self.cancel_request.set()
        for tasks in aio.all_tasks():
            tasks.cancel()

    async def main_loop(self):
        logger.info("Starting SolarEdge2MQTT service...")
        logger.info("Version: {version}", version=__version__)
        logger.info(
            f"Operationg system: {platform.platform()} ({platform.system()}/{platform.machine()})"
        )
        logger.debug(self.settings)
        logger.info("Timezone: {timezone}", timezone=LOCAL_TZ)

        if self.settings.is_influxdb_configured:
            self.influxdb.initialize_buckets()

        while not self.cancel_request.is_set():
            try:
                self.mqtt = MQTTClient(self.settings.mqtt, self.event_bus)

                async with self.mqtt:
                    await self.mqtt.publish_status_online()

                    if self.settings.is_homeassistant_configured:
                        await self.homeassistant.async_init()

                    self._start_mqtt_listener()
                    self.schedule_loop(1, self.timer.loop)

                    await aio.gather(*self.loops)
            except MqttError:
                logger.error("MQTT error, reconnecting in 5 seconds...")
            except aio.exceptions.CancelledError:
                logger.debug("Loops cancelled")
            finally:
                await self.finalize()

            if not self.cancel_request.is_set():
                await aio.sleep(5)

    async def finalize(self):
        try:
            await self.mqtt.publish_status_offline()
        except MqttError:
            pass

        try:
            self.event_bus.cancel_tasks()
        finally:
            pass

        for task in self.loops:
            try:
                task.cancel()
            finally:
                pass

    def _start_mqtt_listener(self):
        task = aio.create_task(self.mqtt.listen())
        self.loops.add(task)
        task.add_done_callback(self.loops.remove)

    def schedule_loop(
        self,
        interval_in_seconds: int,
        handles: Callable | list[Callable],
        delay_start: int = 0,
        args: list[any] = None,
    ):
        loop = aio.create_task(
            self.run_loop(interval_in_seconds, handles, delay_start, args)
        )
        self.loops.add(loop)
        loop.add_done_callback(self.loops.remove)

    async def run_loop(
        self,
        interval_in_seconds: int,
        handles: Callable | list[Callable],
        delay_start: int = 0,
        args: list[any] = None,
    ):
        if not isinstance(handles, list):
            handles = [handles]

        await aio.sleep(delay_start)

        while not self.cancel_request.is_set():
            execution_time = 0
            start_time = time()
            for handle in handles:
                await handle(*args or [])
            execution_time = time() - start_time

            if execution_time < interval_in_seconds:
                await aio.sleep(interval_in_seconds - execution_time)
            else:
                await aio.sleep(interval_in_seconds)
