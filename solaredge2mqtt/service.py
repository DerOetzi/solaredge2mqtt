import asyncio
import json
import signal
from typing import Dict, Tuple

from gmqtt import Client as MQTTClient
from gmqtt import Message as MQTTMessage
from solaredge_modbus import Inverter

from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.models import PowerFlow
from solaredge2mqtt.models.sunspec import SunSpecBattery, SunSpecInverter, SunSpecMeter

STOP = asyncio.Event()

RawData = Dict[str, Dict[str, int | float]]

settings = service_settings()


def run():
    initialize_logging(settings.logging_level)

    logger.info("Starting SolarEdge2MQTT service...")

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, ask_stop)
    loop.add_signal_handler(signal.SIGTERM, ask_stop)
    loop.run_until_complete(main())
    loop.close()


def ask_stop():
    logger.info("Stopping SolarEdge2MQTT service...")
    STOP.set()


async def main():
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
        f"{settings.mqtt_topic_prefix}/status", b"offline", qos=1, retain=True
    )
    client = MQTTClient(settings.mqtt_client_id, will_message=will_message)
    client.set_auth_credentials(settings.mqtt_username, settings.mqtt_password)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    await client.connect(settings.mqtt_broker, settings.mqtt_port)

    while not STOP.is_set():
        inverter_raw, meters_raw, batteries_raw = read_from_modbus(inverter)

        inverter_data = read_inverter(inverter_raw)
        meters_data = read_inverter_meters(meters_raw)
        batteries_data = read_inverter_batteries(batteries_raw)

        powerflow = calc_powerflow(inverter_data, meters_data, batteries_data)

        logger.info(
            "Powerflow:\n{powerflow}", powerflow=powerflow.model_dump_json(indent=4)
        )

        client.publish(
            f"{settings.mqtt_topic_prefix}/inverter",
            inverter_data.model_dump_json(),
            qos=1,
        )

        for meter_key, meter_data in meters_data.items():
            client.publish(
                f"{settings.mqtt_topic_prefix}/meter/{meter_key.lower()}",
                meter_data.model_dump_json(),
                qos=1,
            )

        for battery_key, battery_data in batteries_data.items():
            client.publish(
                f"{settings.mqtt_topic_prefix}/battery/{battery_key.lower()}",
                battery_data.model_dump_json(),
                qos=1,
            )

        client.publish(
            f"{settings.mqtt_topic_prefix}/powerflow",
            powerflow.model_dump_json(),
            qos=1,
        )

        await asyncio.sleep(settings.interval)

    logger.info("SolarEdge2MQTT service stopped")
    await client.disconnect()


def on_connect(client, flags, rc, properties):
    logger.info("Connected to MQTT broker")
    client.publish(f"{settings.mqtt_topic_prefix}/status", "online", qos=1, retain=True)


def on_disconnect(client, packet, exc=None):
    logger.info("Disconnected from MQTT broker")


def read_from_modbus(
    inverter: SunSpecInverter,
) -> Tuple[RawData, Dict[str, RawData], Dict[str, RawData]]:
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


def read_inverter(inverter_raw: RawData) -> SunSpecInverter:
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


def read_inverter_meters(meters_raw: Dict[str, RawData]) -> Dict[str, SunSpecMeter]:
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
            "{meter_key} ({info.manufacturer} {info.model} {info.serialnumber}): {power} W",
            meter_key=meter_key,
            info=meter_data.info,
            power=meter_data.power.power,
        )

        meters[meter_key] = meter_data

    return meters


def read_inverter_batteries(
    batteries_raw: Dict[str, RawData]
) -> Dict[str, SunSpecBattery]:
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
            "{battery_key} ({info.manufacturer} {info.model} {info.serialnumber}): {status}, {power} W, {state_of_charge} %",
            battery_key=battery,
            info=battery_data.info,
            status=battery_data.status,
            power=battery_data.power,
            state_of_charge=battery_data.state_of_charge,
        )

        batteries[battery] = battery_data

    return batteries


def calc_powerflow(inverter, meters, batteries) -> PowerFlow:
    grid = 0
    for meter in meters.values():
        if "Import" in meter.info.option and "Export" in meter.info.option:
            grid += meter.power.power

    batteries_power = 0
    for battery in batteries.values():
        batteries_power += battery.power

    if inverter.dc.power > 0:
        pv_production = inverter.dc.power + batteries_power
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
