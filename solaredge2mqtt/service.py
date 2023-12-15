import asyncio
import json
import signal

from typing import Dict

from solaredge_modbus import Inverter

from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.models.sunspec import SunSpecBattery, SunSpecInverter, SunSpecMeter

STOP = asyncio.Event()


async def main(settings):
    inverter = Inverter(
        host=settings.modbus_host,
        port=settings.modbus_port,
        timeout=settings.modbus_timeout,
        unit=settings.modbus_unit,
    )

    logger.info(
        "Using SolarEdge inverter via modbus: {host}:{port}",
        host=settings.modbus_host,
        port=settings.modbus_port,
    )

    while not STOP.is_set():
        inverter_data = read_inverter(inverter)

        meters_data = read_inverter_meters(inverter)

        batteries_data = read_inverter_batteries(inverter)

        await asyncio.sleep(settings.interval)

    logger.info("SolarEdge2MQTT service stopped")


def read_inverter(inverter) -> SunSpecInverter:
    inverter_raw = inverter.read_all()
    logger.debug(
        "Inverter raw:\n{raw}",
        raw=json.dumps(inverter_raw, indent=4),
    )

    inverter_data = SunSpecInverter(inverter_raw)
    logger.debug(inverter_data)
    logger.info(
        "Inverter ({info.manufacturer} {info.model} {info.serialnumber}): {status}, AC {power_ac} W, DC {power_dc} W, {energy_total} kWh",
        info=inverter_data.info,
        status=inverter_data.status,
        power_ac=inverter_data.ac.power.power,
        power_dc=inverter_data.dc.power,
        energy_total=round(inverter_data.energy_total / 1000, 2),
    )

    return inverter_data


def read_inverter_meters(inverter) -> Dict[str, SunSpecMeter]:
    meters = {}
    for meter_key, meter_obj in inverter.meters().items():
        meter_raw = meter_obj.read_all()
        logger.debug(
            "Meter {meter} raw:\n{raw}",
            meter=meter_key,
            raw=json.dumps(meter_raw, indent=4),
        )

        meter_data = SunSpecMeter(meter_raw)
        logger.debug(meter_data)
        logger.info(
            "{meter_key} ({info.manufacturer} {info.model} {info.serialnumber}): {power} W",
            meter_key=meter_key,
            info=meter_data.info,
            power=meter_data.power.power,
        )

        meters[meter_key] = meter_data

    return meters


def read_inverter_batteries(inverter) -> Dict[str, SunSpecBattery]:
    batteries = {}

    for battery, battery_obj in inverter.batteries().items():
        battery_raw = battery_obj.read_all()
        logger.debug(
            "Battery {battery} raw:\n{raw}",
            battery=battery,
            raw=json.dumps(battery_raw, indent=4),
        )

        battery_data = SunSpecBattery(battery_raw)
        logger.debug(battery_data)
        logger.info(
            "{battery_key} ({info.manufacturer} {info.model} {info.serialnumber}): {status}, {power} W, {state_of_charge} %",
            battery_key=battery,
            info=battery_data.info,
            status=battery_data.status,
            power=battery_data.power,
            state_of_charge=battery_data.state_of_charge,
        )

        batteries[battery] = battery_data

    return batteries


def ask_stop():
    logger.info("Stopping SolarEdge2MQTT service...")
    STOP.set()


def run():
    settings = service_settings()

    initialize_logging(settings.logging_level)

    logger.info("Starting SolarEdge2MQTT service...")

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, ask_stop)
    loop.add_signal_handler(signal.SIGTERM, ask_stop)
    loop.run_until_complete(main(settings))
    loop.close()
