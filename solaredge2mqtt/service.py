"""
    This module, service.py, is part of the SolarEdge2MQTT service, which reads data 
    from a SolarEdge inverter and publishes it to an MQTT broker. It uses the asyncio 
    library for asynchronous I/O and the gmqtt library for MQTT communication. 
    The module also includes a run function to initialize and start the service.
"""
import asyncio
import json
import signal
from typing import Dict, Tuple

from gmqtt import Client as MQTTClient
from gmqtt import Message as MQTTMessage
from solaredge_modbus import Inverter

from solaredge2mqtt.core.logging import LOGGING_DEVICE_INFO, initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.models import PowerFlow
from solaredge2mqtt.models.sunspec import SunSpecBattery, SunSpecInverter, SunSpecMeter

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

    will_message = MQTTMessage(
        f"{settings.topic_prefix}/status",
        b"offline",
        qos=1,
        retain=True,
        will_delay_interval=10,
    )
    client = MQTTClient(settings.client_id, will_message=will_message)
    client.set_auth_credentials(settings.username, settings.password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    await client.connect(settings.broker, settings.port)

    while not STOP.is_set():
        inverter_raw, meters_raw, batteries_raw = read_from_modbus(inverter)

        inverter_data = map_inverter(inverter_raw)
        meters_data = map_inverter_meters(meters_raw)
        batteries_data = map_inverter_batteries(batteries_raw)

        powerflow = calc_powerflow(inverter_data, meters_data, batteries_data)

        logger.debug(powerflow)
        logger.info(
            "Powerflow: PV {pv_production} W, Inverter {inverter} W, House {house_consumption} W, "
            + "Grid {grid} W, Battery {battery} W",
            pv_production=powerflow.pv_production,
            inverter=powerflow.inverter,
            house_consumption=powerflow.house_consumption,
            grid=powerflow.grid,
            battery=powerflow.battery,
        )

        client.publish(
            f"{settings.topic_prefix}/inverter",
            inverter_data.model_dump_json(),
            qos=1,
        )

        for meter_key, meter_data in meters_data.items():
            client.publish(
                f"{settings.topic_prefix}/meter/{meter_key.lower()}",
                meter_data.model_dump_json(),
                qos=1,
            )

        for battery_key, battery_data in batteries_data.items():
            client.publish(
                f"{settings.topic_prefix}/battery/{battery_key.lower()}",
                battery_data.model_dump_json(),
                qos=1,
            )

        client.publish(
            f"{settings.topic_prefix}/powerflow",
            powerflow.model_dump_json(),
            qos=1,
        )

        await asyncio.sleep(settings.interval)

    logger.info("SolarEdge2MQTT service stopped")
    await client.disconnect()


def on_connect(client, flags, rc, properties):
    # pylint: disable=unused-argument
    """Publishes the online status to the MQTT broker on connect."""
    logger.info("Connected to MQTT broker")
    client.publish(f"{settings.topic_prefix}/status", "online", qos=1, retain=True)


def on_disconnect(client, packet, exc=None):
    # pylint: disable=unused-argument
    """Log the disconnection from the MQTT broker."""
    logger.info("Disconnected from MQTT broker")


def read_from_modbus(
    inverter: SunSpecInverter,
) -> Tuple[RawData, Dict[str, RawData], Dict[str, RawData]]:
    """Reads data from the SolarEdge inverter via modbus."""
    inverter_raw = inverter.read_all()
    meters_raw = {
        meter_key: meter_obj.read_all()
        for meter_key, meter_obj in inverter.meters().items()
    }
    batteries_raw = {
        battery_key: battery_obj.read_all()
        for battery_key, battery_obj in inverter.batteries().items()
    }

    return inverter_raw, meters_raw, batteries_raw


def map_inverter(inverter_raw: RawData) -> SunSpecInverter:
    """Map the modbus data to a SunSpecInverter object."""
    logger.debug(
        "Inverter raw:\n{raw}",
        raw=json.dumps(inverter_raw, indent=4),
    )

    inverter_data = SunSpecInverter(inverter_raw)
    logger.debug(inverter_data)
    logger.info(
        LOGGING_DEVICE_INFO
        + ": {status}, AC {power_ac} W, DC {power_dc} W, {energy_total} kWh",
        device="Inverter",
        info=inverter_data.info,
        status=inverter_data.status,
        power_ac=inverter_data.ac.power.power,
        power_dc=inverter_data.dc.power,
        energy_total=round(inverter_data.energy_total / 1000, 2),
    )

    return inverter_data


def map_inverter_meters(meters_raw: Dict[str, RawData]) -> Dict[str, SunSpecMeter]:
    """Map the modbus data to SunSpecMeter objects."""
    meters = {}
    for meter_key, meter_raw in meters_raw.items():
        logger.debug(
            "Meter {meter} raw:\n{raw}",
            meter=meter_key,
            raw=json.dumps(meter_raw, indent=4),
        )

        meter_data = SunSpecMeter(meter_raw)
        logger.debug(meter_data)
        logger.info(
            LOGGING_DEVICE_INFO + ": {power} W",
            device=meter_key,
            info=meter_data.info,
            power=meter_data.power.power,
        )

        meters[meter_key] = meter_data

    return meters


def map_inverter_batteries(
    batteries_raw: Dict[str, RawData]
) -> Dict[str, SunSpecBattery]:
    """Map the modbus data to SunSpecBattery objects.""" ""
    batteries = {}

    for battery, battery_raw in batteries_raw.items():
        logger.debug(
            "Battery {battery} raw:\n{raw}",
            battery=battery,
            raw=json.dumps(battery_raw, indent=4),
        )

        battery_data = SunSpecBattery(battery_raw)
        logger.debug(battery_data)
        logger.info(
            LOGGING_DEVICE_INFO + ": {status}, {power} W, {state_of_charge} %",
            device=battery,
            info=battery_data.info,
            status=battery_data.status,
            power=battery_data.power,
            state_of_charge=battery_data.state_of_charge,
        )

        batteries[battery] = battery_data

    return batteries


def calc_powerflow(inverter, meters, batteries) -> PowerFlow:
    """
    Calculates the power flow in the system by summing the power of all meters and batteries.
    It considers both import and export options for each meter in the calculation.
    Returns a PowerFlow object representing the total power flow in the system.
    """
    grid = 0
    for meter in meters.values():
        if "Import" in meter.info.option and "Export" in meter.info.option:
            grid += meter.power.power

    batteries_power = 0
    for battery in batteries.values():
        batteries_power += battery.power

    if inverter.dc.power > 0:
        pv_production = inverter.dc.power + batteries_power
        if pv_production < 0:
            pv_production = 0
        inverter_consumption = inverter.dc.power - inverter.ac.power.power
        inverter_delivery = inverter.ac.power.power
    else:
        pv_production = 0
        inverter_consumption = abs(inverter.ac.power.power)
        inverter_delivery = 0

    inverter = inverter.ac.power.power

    if grid >= 0:
        grid_consumption = 0
        grid_delivery = grid
    else:
        grid_consumption = abs(grid)
        grid_delivery = 0

    battery = batteries_power
    if battery >= 0:
        battery_charge = battery
        battery_discharge = 0
    else:
        battery_charge = 0
        battery_discharge = abs(battery)

    house_consumption = int(abs(grid - inverter))

    return PowerFlow(
        pv_production=int(pv_production),
        inverter=int(inverter),
        inverter_consumption=int(inverter_consumption),
        inverter_delivery=int(inverter_delivery),
        house_consumption=int(house_consumption),
        grid=int(grid),
        grid_consumption=int(grid_consumption),
        grid_delivery=int(grid_delivery),
        battery=int(battery),
        battery_charge=int(battery_charge),
        battery_discharge=int(battery_discharge),
    )
