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

from solaredge2mqtt import __version__
from solaredge2mqtt.eventbus import EventBus
from solaredge2mqtt.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.logging import initialize_logging, logger
from solaredge2mqtt.models.base import (
    Interval10MinTriggerEvent,
    IntervalBaseTriggerEvent,
)
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.service.base import BaseLoops
from solaredge2mqtt.service.forecast import ForecastService
from solaredge2mqtt.service.homeassistant import HomeAssistantDiscovery
from solaredge2mqtt.service.influxdb import InfluxDB
from solaredge2mqtt.service.monitoring import MonitoringSite
from solaredge2mqtt.service.weather import WeatherClient
from solaredge2mqtt.settings import LOCAL_TZ, service_settings


def run():
    try:
        service = Service()
        loop = aio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, service.cancel)
        loop.add_signal_handler(signal.SIGTERM, service.cancel)
        loop.run_until_complete(service.main_loop())
        loop.close()
    except ConfigurationException:
        logger.error("Configuration error")


class Service:
    def __init__(self):
        self.settings = service_settings()
        initialize_logging(self.settings.logging_level)
        logger.debug(self.settings)

        self.event_bus = EventBus()

        self.mqtt = MQTTClient(self.settings.mqtt, self.event_bus)

        self.cancel_request = aio.Event()
        self.loops: set[aio.Task] = set()

        self.influxdb: InfluxDB | None = (
            InfluxDB(self.settings.influxdb, self.settings.prices, self.event_bus)
            if self.settings.is_influxdb_configured
            else None
        )

        self.basics = BaseLoops(self.settings, self.event_bus, self.influxdb)

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
        for loop in self.loops:
            loop.cancel()

        self.event_bus.cancel_tasks()

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
                async with self.mqtt:
                    await self.mqtt.publish_status_online()

                    self.schedule_loop(
                        self.settings.interval, self.interval_base_trigger
                    )
                    self.schedule_loop(600, self.interval_10_minute_trigger)
                    # await self._start_mqtt_listener()

                    await aio.gather(*self.loops)

                    await self.mqtt.publish_status_offline()

            except MqttError:
                logger.error("MQTT error, reconnecting in 5 seconds...")
                await aio.sleep(5)
            except aio.exceptions.CancelledError:
                logger.debug("Loops cancelled")
                return
            finally:
                for loop in self.loops:
                    loop.cancel()

    async def interval_base_trigger(self):
        await self.event_bus.emit(IntervalBaseTriggerEvent())

    async def interval_10_minute_trigger(self):
        await self.event_bus.emit(Interval10MinTriggerEvent())

    # async def _start_mqtt_listener(self):
    #     mqtt_topics = [
    #         event.topic
    #         for event in self.event_bus.subcribed_events
    #         if isinstance(event, MQTTReceivedEvent)
    #     ]
    #     await self.mqtt.subscribe_topics(mqtt_topics)
    #     if mqtt_topics:
    #         task = aio.create_task(self.mqtt.listen())
    #         self.loops.add(task)
    #         task.add_done_callback(self.loops.remove)

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
