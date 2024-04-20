import json

from aiomqtt import Client, Will
from pydantic import BaseModel

from solaredge2mqtt.eventbus import EventBus
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import MQTTPublishEvent, MQTTReceivedEvent
from solaredge2mqtt.settings import MQTTSettings


class MQTTClient(Client):
    def __init__(self, settings: MQTTSettings, event_bus: EventBus):
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

        self.event_bus = event_bus
        self._subscribe_events()

        super().__init__(
            self.broker,
            self.port,
            username=settings.username,
            password=settings.password.get_secret_value(),
            identifier=settings.client_id,
            will=will,
        )

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(MQTTPublishEvent, self.event_listener)

    async def listen(self) -> None:
        logger.info("MQTT listen on subscribed topics")
        async for message in self.messages:
            logger.debug(
                "MQTT message topic: {message.topic}={message.payload}",
                message=message,
            )
            payload = json.loads(message.payload.decode())
            await self.event_bus.emit(
                MQTTReceivedEvent(topic=str(message.topic), payload=payload)
            )

    async def publish_status_online(self) -> None:
        await self.publish_to("status", "online", True)

    async def publish_status_offline(self) -> None:
        await self.publish_to("status", "offline", True)

    async def event_listener(self, event: MQTTPublishEvent) -> None:
        await self.publish_to(
            event.topic,
            event.payload,
            event.retain,
            event.qos,
            event.topic_prefix,
            event.exclude_none,
        )

    async def publish_to(
        self,
        topic: str,
        payload: str | int | float | BaseModel,
        retain: bool = False,
        qos: int = 1,
        topic_prefix: str | None = None,
        exclude_none: bool = False,
    ) -> None:
        if self._connected:
            topic = f"{topic_prefix or self.topic_prefix}/{topic}"

            if isinstance(payload, BaseModel):
                payload = payload.model_dump_json(exclude_none=exclude_none)

            await self.publish(topic, payload, qos=qos, retain=retain)
