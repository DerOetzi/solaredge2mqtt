"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the gmqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""
import asyncio
import signal
from typing import Dict

from solaredge2mqtt.api import MonitoringSite
from solaredge2mqtt.logging import initialize_logging, logger
from solaredge2mqtt.modbus import Modbus
from solaredge2mqtt.mqtt import MQTT
from solaredge2mqtt.settings import service_settings

STOP = asyncio.Event()

RawData = Dict[str, Dict[str, int | float]]

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

    if settings.is_api_configured:
        monitoring = MonitoringSite(settings)
        monitoring.login()
        monitoring.get_energies()

    while not STOP.is_set():
        inverter_data, meters_data, batteries_data = modbus.loop()

        powerflow = Modbus.calc_powerflow(inverter_data, meters_data, batteries_data)

        mqtt.publish_inverter(inverter_data)
        mqtt.publish_meters(meters_data)
        mqtt.publish_batteries(batteries_data)
        mqtt.publish_powerflow(powerflow)

        await asyncio.sleep(settings.interval)

    logger.info("SolarEdge2MQTT service stopped")
    await mqtt.disconnect()


def on_connect(client, flags, rc, properties):
    # pylint: disable=unused-argument
    """Publishes the online status to the MQTT broker on connect."""
    logger.info("Connected to MQTT broker")
    client.publish(f"{settings.topic_prefix}/status", "online", qos=1, retain=True)


def on_disconnect(client, packet, exc=None):
    # pylint: disable=unused-argument
    """Log the disconnection from the MQTT broker."""
    logger.info("Disconnected from MQTT broker")
