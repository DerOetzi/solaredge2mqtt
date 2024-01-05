from typing import Dict

from gmqtt import Client, Message
from pydantic import BaseModel

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import (
    LogicalModule,
    Powerflow,
    SunSpecBattery,
    SunSpecInverter,
    SunSpecMeter,
    WallboxAPI,
)
from solaredge2mqtt.settings import ServiceSettings


class MQTTClient:
    def __init__(self, settings: ServiceSettings):
        self.broker = settings.broker
        self.port = settings.port

        self.topic_prefix = settings.topic_prefix

        logger.info(
            "Using MQTT broker: {broker}:{port}",
            broker=settings.broker,
            port=settings.port,
        )

        self.connected = False

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
        self.connected = True

    def on_disconnect(self, client: Client, packet, exc=None) -> None:
        # pylint: disable=unused-argument
        logger.info("Disconnected from MQTT broker")
        self.connected = False

    def publish_inverter(self, inverter: SunSpecInverter) -> None:
        self._publish("modbus/inverter", inverter)

    def publish_meters(self, meters: Dict[str, SunSpecMeter]) -> None:
        for meter_key, meter in meters.items():
            self._publish(f"modbus/meter/{meter_key.lower()}", meter)

    def publish_batteries(self, batteries: Dict[str, SunSpecBattery]) -> None:
        for battery_key, battery in batteries.items():
            self._publish(f"modbus/battery/{battery_key.lower()}", battery)

    def publish_wallbox(self, wallbox: WallboxAPI) -> None:
        self._publish("rest/wallbox", wallbox)

    def publish_powerflow(self, powerflow: Powerflow) -> None:
        self._publish("powerflow", powerflow)

    def publish_pv_energy_today(self, energy: int) -> None:
        self._publish("api/monitoring/pv_energy_today", energy)

    def publish_module_energy(self, modules: list[LogicalModule]) -> None:
        for module in modules:
            self._publish(
                f"api/monitoring/module/{module.info.serialnumber}",
                module,
            )

    def _publish(self, topic: str, payload: str | int | float | BaseModel) -> None:
        if self.connected:
            if isinstance(payload, BaseModel):
                payload = payload.model_dump_json()
            self.client.publish(f"{self.topic_prefix}/{topic}", payload, qos=1)
