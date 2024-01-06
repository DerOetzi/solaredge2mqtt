"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the gmqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""
import asyncio
import signal
import datetime as dt

from typing import Optional

from scheduler.asyncio import Scheduler

from solaredge2mqtt.api import MonitoringSite
from solaredge2mqtt.logging import initialize_logging, logger
from solaredge2mqtt.influxdb import InfluxDB
from solaredge2mqtt.modbus import Modbus
from solaredge2mqtt.models import Powerflow
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.wallbox import WallboxClient
from solaredge2mqtt.settings import service_settings

STOP = asyncio.Event()

settings = service_settings()


def run():
    """Initializes and starts the SolarEdge2MQTT service."""
    initialize_logging(settings.logging_level)

    logger.info("Starting SolarEdge2MQTT service...")

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, ask_stop)
    loop.add_signal_handler(signal.SIGTERM, ask_stop)
    loop.run_until_complete(main())
    loop.close()


def ask_stop():
    """Stops the SolarEdge2MQTT service by setting the STOP event."""
    logger.info("Stopping SolarEdge2MQTT service...")
    STOP.set()


async def main():
    """
    Initializes the SolarEdge inverter and logs the connection details.
    This function is the main entry point for the SolarEdge2MQTT service.
    """

    modbus = Modbus(settings)

    if settings.is_wallbox_configured:
        wallbox = WallboxClient(settings)
    else:
        wallbox = None

    if settings.is_influxdb_configured:
        influxdb = InfluxDB(settings)
        influxdb.initialize_buckets()
        influxdb.initialize_task()
    else:
        influxdb = None

    mqtt = MQTTClient(settings)

    await mqtt.connect()

    loop = asyncio.get_running_loop()
    scheduler = Scheduler(loop=loop)
    scheduler.cyclic(
        dt.timedelta(seconds=settings.interval),
        modbus_and_wallbox_loop,
        args=[modbus, mqtt, wallbox, influxdb],
    )

    if settings.is_api_configured:
        monitoring = MonitoringSite(settings)
        monitoring.login()
        await energy_loop(monitoring, mqtt)
        scheduler.cyclic(
            dt.timedelta(seconds=300), energy_loop, args=[monitoring, mqtt]
        )

    logger.debug(scheduler)

    while not STOP.is_set():
        await asyncio.sleep(1)

    scheduler.delete_jobs()
    await mqtt.disconnect()


modbus_lock = asyncio.Lock()


async def modbus_and_wallbox_loop(
    modbus: Modbus,
    mqtt: MQTTClient,
    wallbox: Optional[WallboxClient] = None,
    influxdb: Optional[InfluxDB] = None,
):
    if modbus_lock.locked():
        logger.warning("Modbus is still locked, skipping this loop")
        return

    async with modbus_lock:
        results = await asyncio.gather(
            modbus.loop(),
            wallbox.loop() if settings.is_wallbox_configured else asyncio.sleep(0),
        )

        inverter_data, meters_data, batteries_data = results[0]

        if any(data is None for data in [inverter_data, meters_data, batteries_data]):
            logger.warning("Invalid modbus data, skipping this loop")
            return

        wallbox_data = results[1]
        evcharger = 0

        if wallbox_data is not None:
            evcharger = wallbox_data.power

        powerflow = Powerflow.calc(
            inverter_data, meters_data, batteries_data, evcharger
        )
        if not powerflow.consumer.is_valid:
            logger.warning("Invalid powerflow data: {powerflow}", powerflow=powerflow)

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

        mqtt.publish_inverter(inverter_data)
        mqtt.publish_meters(meters_data)
        mqtt.publish_batteries(batteries_data)
        mqtt.publish_powerflow(powerflow)

        if wallbox_data is not None:
            mqtt.publish_wallbox(wallbox_data)

        if influxdb is not None:
            influxdb.write_components(
                inverter_data, meters_data, batteries_data, wallbox_data
            )

            influxdb.write_powerflow(powerflow)
            influxdb.flush_loop()


energy_lock = asyncio.Lock()


async def energy_loop(monitoring: MonitoringSite, mqtt: MQTTClient):
    """Publishes the energy data from monitoring site to the MQTT broker."""
    if energy_lock.locked():
        logger.warning("Energy is still locked, skipping this loop")
        return

    async with energy_lock:
        modules = monitoring.get_module_energies()

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

        mqtt.publish_pv_energy_today(energy_total)
        mqtt.publish_module_energy(modules)
