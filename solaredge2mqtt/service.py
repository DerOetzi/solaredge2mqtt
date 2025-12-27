"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the aiomqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""

import asyncio
import platform
import signal
from time import time
from typing import Callable

from aiomqtt import MqttError
from tzlocal import get_localzone_name

from solaredge2mqtt import __version__
from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.influxdb import InfluxDBAsync
from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.mqtt import MQTTClient
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.core.timer import Timer
from solaredge2mqtt.services.energy import EnergyService
from solaredge2mqtt.services.forecast import FORECAST_AVAILABLE
from solaredge2mqtt.services.homeassistant import HomeAssistantDiscovery
from solaredge2mqtt.services.monitoring import MonitoringSite
from solaredge2mqtt.services.powerflow import PowerflowService
from solaredge2mqtt.services.weather import WeatherClient

if FORECAST_AVAILABLE:
    from solaredge2mqtt.services.forecast import ForecastService

LOCAL_TZ = get_localzone_name()


async def _run_service() -> None:
    service = Service()
    await service.run()


def run():
    try:
        asyncio.run(_run_service())
    except ConfigurationException:
        logger.error("Configuration error")
    except asyncio.CancelledError:
        logger.debug("Service cancelled")
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")


class Service:
    def __init__(self):
        self.settings = service_settings()
        initialize_logging(self.settings.logging_level)
        logger.debug(self.settings)

        self.event_bus = EventBus()
        self.timer = Timer(self.event_bus, self.settings.interval)

        self.mqtt: MQTTClient | None = None

        self.cancel_request = asyncio.Event()
        self.loops: set[asyncio.Task] = set()
        self._run_task: asyncio.Task | None = None

        self.influxdb: InfluxDBAsync | None = (
            InfluxDBAsync(self.settings.influxdb,
                          self.settings.prices, self.event_bus)
            if self.settings.is_influxdb_configured
            else None
        )

        self.energy: EnergyService | None = (
            EnergyService(self.settings.energy, self.event_bus, self.influxdb)
            if self.settings.is_influxdb_configured
            else None
        )

        self.powerflow = PowerflowService(
            self.settings, self.event_bus, self.influxdb)

        self.monitoring: MonitoringSite | None = (
            MonitoringSite(self.settings.monitoring,
                           self.event_bus, self.influxdb)
            if self.settings.is_monitoring_configured
            else None
        )

        self.weather: WeatherClient | None = (
            WeatherClient(self.settings, self.event_bus)
            if self.settings.is_weather_configured
            else None
        )

        self.forecast: ForecastService | None = None
        if FORECAST_AVAILABLE:
            self.forecast = (
                ForecastService(
                    self.settings.forecast,
                    self.settings.location,
                    self.event_bus,
                    self.influxdb,
                )
                if self.settings.is_forecast_configured
                else None
            )
        elif self.settings.is_forecast_configured:
            logger.warning(
                "Forecast service not available, please refer to README")

        self.homeassistant: HomeAssistantDiscovery | None = (
            HomeAssistantDiscovery(self.settings, self.event_bus)
            if self.settings.is_homeassistant_configured
            else None
        )

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self._run_task = asyncio.current_task()
        self._register_signal_handlers(loop)
        try:
            await self.main_loop()
        finally:
            await self.shutdown()

    def _register_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(signum, self.cancel)

    def cancel(self):
        logger.info("Stopping SolarEdge2MQTT service...")

        if self.cancel_request.is_set():
            return

        self.cancel_request.set()

        if self._run_task is not None:
            self._run_task.cancel()

        for task in self.loops:
            task.cancel()

    async def main_loop(self):
        logger.info("Starting SolarEdge2MQTT service...")
        logger.info("Version: {version}", version=__version__)
        logger.info(
            f"Operationg system: {platform.platform()} "
            f"({platform.system()}/{platform.machine()})"
        )
        logger.debug(self.settings)
        logger.info("Timezone: {timezone}", timezone=LOCAL_TZ)

        if self.settings.is_influxdb_configured:
            self.influxdb.init()

        while not self.cancel_request.is_set():
            try:
                self.mqtt = MQTTClient(self.settings.mqtt, self.event_bus)

                async with self.mqtt:
                    await self.mqtt.publish_status_online()

                    if self.settings.is_homeassistant_configured:
                        await self.homeassistant.async_init()

                    await self.powerflow.async_init()

                    self._start_mqtt_listener()
                    self.schedule_loop(1, self.timer.loop)

                    await asyncio.gather(*self.loops)
            except MqttError:
                if self.cancel_request.is_set():
                    break
                logger.error("MQTT error, reconnecting in 5 seconds...")
            except asyncio.CancelledError:
                logger.debug("Loops cancelled")
                raise
            finally:
                await self.finalize()

            if self.cancel_request.is_set():
                break

            await asyncio.sleep(5)

    async def _stop_loops(self) -> None:
        if not self.loops:
            return

        tasks = list(self.loops)
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        self.loops.clear()

    async def finalize(self):
        await self._stop_loops()

        if self.mqtt is not None:
            try:
                await self.mqtt.publish_status_offline()
            except MqttError:
                logger.debug(
                    "Unable to publish offline status during cleanup"
                )
            finally:
                self.mqtt = None

        await self.event_bus.cancel_tasks()

    async def shutdown(self) -> None:
        await self.finalize()
        await self.close()

    def _start_mqtt_listener(self):
        task = asyncio.create_task(self.mqtt.listen())
        self.loops.add(task)
        task.add_done_callback(self.loops.discard)

        task = asyncio.create_task(self.mqtt.process_queue())
        self.loops.add(task)
        task.add_done_callback(self.loops.discard)

    def schedule_loop(
        self,
        interval_in_seconds: int,
        handles: Callable | list[Callable],
        delay_start: int = 0,
        args: list[any] = None,
    ):
        loop = asyncio.create_task(
            self.run_loop(interval_in_seconds, handles, delay_start, args)
        )
        self.loops.add(loop)
        loop.add_done_callback(self.loops.discard)

    async def run_loop(
        self,
        interval_in_seconds: int,
        handles: Callable | list[Callable],
        delay_start: int = 0,
        args: list[any] = None,
    ):
        if not isinstance(handles, list):
            handles = [handles]

        await asyncio.sleep(delay_start)

        while not self.cancel_request.is_set():
            execution_time = 0
            start_time = time()
            for handle in handles:
                await handle(*args or [])
            execution_time = time() - start_time

            if execution_time < interval_in_seconds:
                await asyncio.sleep(interval_in_seconds - execution_time)
            else:
                await asyncio.sleep(interval_in_seconds)

    async def close(self):
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *[
                        service.close()
                        for service in [
                            self.influxdb,
                            self.powerflow,
                            self.monitoring,
                            self.weather,
                        ]
                        if service
                    ]
                ),
                timeout=5
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Timeout while closing tasks, proceeding with shutdown.")
