from aiomqtt import Client, Will
from pydantic import BaseModel

from solaredge2mqtt.logging import logger
from solaredge2mqtt.settings import MQTTSettings


class MQTTClient(Client):
    def __init__(self, settings: MQTTSettings):
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
            password=settings.password.get_secret_value(),
            identifier=settings.client_id,
            will=will,
        )

    async def publish_status_online(self) -> None:
        await self.publish_to("status", "online", True)

    async def publish_status_offline(self) -> None:
        await self.publish_to("status", "offline", True)

    async def publish_to(
        self,
        topic: str,
        payload: str | int | float | BaseModel,
        retain: bool = False,
        qos: int = 1,
    ) -> None:
        if self._connected:
            if isinstance(payload, BaseModel):
                payload = payload.model_dump_json()
            await self.publish(
                f"{self.topic_prefix}/{topic}", payload, qos=qos, retain=retain
            )
