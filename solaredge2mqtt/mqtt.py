from typing import Dict

from aiomqtt import Client as AsyncClient
from aiomqtt import Will
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


class MQTTClient(AsyncClient):
    def __init__(self, settings: ServiceSettings):
        self.broker = settings.broker
        self.port = settings.port

        self.topic_prefix = settings.topic_prefix

        logger.info(
            "Using MQTT broker: {broker}:{port}",
            broker=settings.broker,
            port=settings.port,
        )

        will = Will(
            topic=f"{self.topic_prefix}/status", payload="offline", qos=1, retain=True
        )

        super().__init__(
            self.broker,
            self.port,
            username=settings.username,
            password=settings.password,
            client_id=settings.client_id,
            will=will,
        )

    async def publish_status_online(self) -> None:
        await self.publish(f"{self.topic_prefix}/status", "online", qos=1, retain=True)

    async def publish_status_offline(self) -> None:
        await self.publish(f"{self.topic_prefix}/status", "offline", qos=1, retain=True)

    async def publish_inverter(self, inverter: SunSpecInverter) -> None:
        await self._publish("modbus/inverter", inverter)

    async def publish_meters(self, meters: Dict[str, SunSpecMeter]) -> None:
        for meter_key, meter in meters.items():
            await self._publish(f"modbus/meter/{meter_key.lower()}", meter)

    async def publish_batteries(self, batteries: Dict[str, SunSpecBattery]) -> None:
        for battery_key, battery in batteries.items():
            await self._publish(f"modbus/battery/{battery_key.lower()}", battery)

    async def publish_wallbox(self, wallbox: WallboxAPI) -> None:
        await self._publish("rest/wallbox", wallbox)

    async def publish_powerflow(self, powerflow: Powerflow) -> None:
        await self._publish("powerflow", powerflow)

    async def publish_pv_energy_today(self, energy: int) -> None:
        await self._publish("api/monitoring/pv_energy_today", energy)

    async def publish_module_energy(self, modules: list[LogicalModule]) -> None:
        for module in modules:
            await self._publish(
                f"api/monitoring/module/{module.info.serialnumber}",
                module,
            )

    async def _publish(
        self, topic: str, payload: str | int | float | BaseModel
    ) -> None:
        if self._connected:
            if isinstance(payload, BaseModel):
                payload = payload.model_dump_json()
            await self.publish(f"{self.topic_prefix}/{topic}", payload, qos=1)
