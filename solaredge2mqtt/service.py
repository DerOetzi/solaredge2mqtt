"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the gmqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""
import asyncio
import signal
from typing import Dict
import datetime as dt

from scheduler.asyncio import Scheduler

from solaredge2mqtt.api import MonitoringSite
from solaredge2mqtt.logging import initialize_logging, logger
from solaredge2mqtt.modbus import Modbus
from solaredge2mqtt.mqtt import MQTT
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

    mqtt = MQTT(settings)

    await mqtt.connect()

    loop = asyncio.get_running_loop()
    scheduler = Scheduler(loop=loop)
    scheduler.cyclic(
        dt.timedelta(seconds=settings.interval), modbus_loop, args=[modbus, mqtt]
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


async def modbus_loop(modbus: Modbus, mqtt: MQTT):
    """Publishes the modbus data to the MQTT broker."""
    inverter_data, meters_data, batteries_data = modbus.loop()

    powerflow = Modbus.calc_powerflow(inverter_data, meters_data, batteries_data)

    mqtt.publish_inverter(inverter_data)
    mqtt.publish_meters(meters_data)
    mqtt.publish_batteries(batteries_data)
    mqtt.publish_powerflow(powerflow)


async def energy_loop(monitoring: MonitoringSite, mqtt: MQTT):
    """Publishes the energy data from monitoring site to the MQTT broker."""
    modules = monitoring.get_module_energies()
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

    mqtt.publish_module_energy(modules)
