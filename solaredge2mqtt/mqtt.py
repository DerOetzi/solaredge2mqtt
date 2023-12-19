from typing import Dict
from gmqtt import Client, Message

from solaredge2mqtt.logging import logger
from solaredge2mqtt.settings import ServiceSettings
from solaredge2mqtt.models import (
    SunSpecInverter,
    SunSpecMeter,
    SunSpecBattery,
    PowerFlow,
    LogicalModule,
)


class MQTT:
    def __init__(self, settings: ServiceSettings):
        self.broker = settings.broker
        self.port = settings.port

        self.topic_prefix = settings.topic_prefix

        logger.info(
            "Using MQTT broker: {broker}:{port}",
            broker=settings.broker,
            port=settings.port,
        )

        will_message = Message(
            f"{settings.topic_prefix}/status",
            b"offline",
            qos=1,
            retain=True,
            will_delay_interval=10,
        )
        self.client = Client(settings.client_id, will_message=will_message)
        self.client.set_auth_credentials(settings.username, settings.password)

        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect

    async def connect(self) -> None:
        await self.client.connect(self.broker, self.port)

    async def disconnect(self) -> None:
        self.client.publish(
            f"{self.topic_prefix}/status", "offline", qos=1, retain=True
        )
        await self.client.disconnect()

    def on_connect(self, client: Client, flags, rc, properties) -> None:
        # pylint: disable=unused-argument
        logger.info("Connected to MQTT broker")

        client.publish(f"{self.topic_prefix}/status", "online", qos=1, retain=True)

    def on_disconnect(self, client: Client, packet, exc=None) -> None:
        # pylint: disable=unused-argument
        logger.info("Disconnected from MQTT broker")

    def publish_inverter(self, inverter: SunSpecInverter) -> None:
        self.client.publish(
            f"{self.topic_prefix}/modbus/inverter",
            inverter.model_dump_json(),
            qos=1,
        )

    def publish_meters(self, meters: Dict[str, SunSpecMeter]) -> None:
        for meter_key, meter in meters.items():
            self.client.publish(
                f"{self.topic_prefix}/modbus/meter/{meter_key.lower()}",
                meter.model_dump_json(),
                qos=1,
            )

    def publish_batteries(self, batteries: Dict[str, SunSpecBattery]) -> None:
        for battery_key, battery in batteries.items():
            self.client.publish(
                f"{self.topic_prefix}/modbus/battery/{battery_key.lower()}",
                battery.model_dump_json(),
                qos=1,
            )

    def publish_powerflow(self, powerflow: PowerFlow) -> None:
        self.client.publish(
            f"{self.topic_prefix}/modbus/powerflow",
            powerflow.model_dump_json(),
            qos=1,
        )

    def publish_module_energy(self, modules: list[LogicalModule]) -> None:
        for module in modules:
            self.client.publish(
                f"{self.topic_prefix}/monitoring/module/{module.info.serialnumber}",
                module.model_dump_json(),
                qos=1,
            )
