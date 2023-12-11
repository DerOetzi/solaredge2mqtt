import asyncio

from solaredge_modbus import Inverter

from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings


async def service_loop(inverter, settings):
    while True:
        values = inverter.read_all()
        logger.info(values)
        await asyncio.sleep(settings.interval)


async def main():
    settings = service_settings()

    initialize_logging(settings.logging_level)

    logger.info("Starting SolarEdge2MQTT service...")

    inverter = Inverter(
        host=settings.modbus_host,
        port=settings.modbus_port,
        timeout=settings.modbus_timeout,
        unit=settings.modbus_unit,
    )

    logger.info(
        "Connecting to SolarEdge inverter via modbus ({host}:{port})...",
        host=settings.modbus_host,
        port=settings.modbus_port,
    )

    await service_loop(inverter, settings)


def run():
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as ex:
        logger.info("Stopping SolarEdge2MQTT service...")
        if isinstance(ex, SystemExit):
            raise ex
