import asyncio

from solaredge_modbus import Inverter

from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.models.sunspec import SunSpecInverter, SunSpecMeter, SunSpecBattery


async def service_loop(inverter, settings):
    while True:
        values = inverter.read_all()
        inverter_data = SunSpecInverter(values)

        logger.info(
            "Inverter data: {inverter_data}",
            inverter_data=inverter_data.model_dump_json(indent=4),
        )

        for meter, params in inverter.meters().items():
            meter_data = SunSpecMeter(params.read_all())
            logger.info(
                "Meter {meter} data: {meter_data}",
                meter=meter,
                meter_data=meter_data.model_dump_json(indent=4),
            )

        for battery, params in inverter.batteries().items():
            battery_data = SunSpecBattery(params.read_all())
            logger.info(
                "Battery {battery} data: {battery_data}",
                battery=battery,
                battery_data=battery_data.model_dump_json(indent=4),
            )

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
