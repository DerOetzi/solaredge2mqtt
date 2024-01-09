from aiomqtt import Client, Will
from pydantic import BaseModel

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import Component, LogicalModule, Powerflow
from solaredge2mqtt.settings import ServiceSettings


class MQTTClient(Client):
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

    async def publish_components(
        self, *args: list[Component | dict[str, Component] | None]
    ) -> None:
        for arg in args:
            if isinstance(arg, dict):
                for component_key, component in arg.items():
                    await self._publish(
                        f"{component.SOURCE}/{component.COMPONENT}/{component_key.lower()}",
                        component,
                    )
            elif isinstance(arg, Component):
                await self._publish(f"{arg.SOURCE}/{arg.COMPONENT}", arg)
            elif arg is None:
                continue
            else:
                raise ValueError(f"Invalid component: {arg}")

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
