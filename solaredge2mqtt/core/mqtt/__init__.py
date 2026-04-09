import json
from asyncio import Queue, QueueFull
from types import TracebackType
from typing import Any, Self

from aiomqtt import Client, Message, Will
from pydantic import BaseModel, ValidationError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import (
    MQTTPublishEvent,
    MQTTReceivedEvent,
    MQTTSubscribeEvent,
)
from solaredge2mqtt.core.mqtt.models import MAX_MQTT_PAYLOAD_SIZE
from solaredge2mqtt.core.mqtt.settings import MQTTSettings


class MQTTClient(Client):
    def __init__(self, settings: MQTTSettings, event_bus: EventBus):
        self.broker = settings.broker
        self.port = settings.port
        self._is_connected = False

        self.topic_prefix = settings.topic_prefix

        logger.info(
            "Using MQTT broker: {broker}:{port}",
            broker=settings.broker,
            port=settings.port,
        )

        will = Will(
            topic=f"{self.topic_prefix}/status", payload="offline", qos=1, retain=True
        )

        self._subscribed_topics: dict[str, type[MQTTReceivedEvent[Any]]] = {}

        self._received_message_queue: Queue[Message] = Queue(maxsize=10)

        self.event_bus = event_bus
        self._subscribe_events()

        super().__init__(
            self.broker,
            self.port,
            will=will,
            **settings.kargs,
        )

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        self._is_connected = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self._is_connected = False
        return await super().__aexit__(exc_type, exc_val, exc_tb)

    def _subscribe_events(self) -> None:
        self.event_bus.unsubscribe_all(MQTTPublishEvent)
        self.event_bus.unsubscribe_all(MQTTSubscribeEvent)

        self.event_bus.subscribe(MQTTPublishEvent, self.event_listener)
        self.event_bus.subscribe(MQTTSubscribeEvent, self._subscribe_topic)

    async def _subscribe_topic(self, event: MQTTSubscribeEvent[Any]) -> None:
        if event.topic not in self._subscribed_topics:
            logger.info(f"Subscribing to topic: {event.topic}")
            self._subscribed_topics[event.topic] = event.event()
            await self.subscribe(event.topic)

    async def listen(self) -> None:
        if self._subscribed_topics:
            async for message in self.messages:
                topic = str(message.topic)
                if topic not in self._subscribed_topics:
                    logger.warning(
                        f"Received message on unsubscribed topic: {topic}")
                    continue
                if len(message.payload) > MAX_MQTT_PAYLOAD_SIZE:
                    logger.warning(
                        f"Payload too large on topic: {topic} "
                        f"({len(message.payload)} bytes)"
                    )
                    continue
                try:
                    self._received_message_queue.put_nowait(message)
                except QueueFull:
                    logger.warning(
                        "MQTT processing queue full – dropping message")

    async def process_queue(self) -> None:
        if self._subscribed_topics:
            while True:
                message = await self._received_message_queue.get()
                try:
                    await self._handle_message(message)
                except Exception as ex:
                    logger.error(f"Error while processing MQTT message: {ex}")

    async def _handle_message(self, message: Message) -> None:
        topic = str(message.topic)
        try:
            event = self._subscribed_topics.get(topic)
            if not event:
                logger.warning(
                    f"Received message for unexpected topic: {topic}")
                return

            payload = message.payload.decode()

            try:
                input_raw = json.loads(payload)
            except json.JSONDecodeError:
                input_raw = json.loads(json.dumps(payload))

            model = event.input_model()

            if isinstance(input_raw, (dict, list, int, float, bool, str)):
                parsed_input = model.model_validate(input_raw)
            else:
                logger.warning(
                    f"Received invalid payload type on topic: {topic}")
                return

            await self.event_bus.emit(event(topic, parsed_input))
        except (ValidationError, json.JSONDecodeError, TypeError) as ex:
            logger.warning(
                f"Received invalid message on topic: {topic}, error: {ex}")

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
        retain: bool,
        qos: int = 1,
        topic_prefix: str | None = None,
        exclude_none: bool = False,
    ) -> None:
        if self._is_connected:
            topic = f"{topic_prefix or self.topic_prefix}/{topic}"
            logger.trace("Publishing to topic: {topic}", topic=topic)

            if isinstance(payload, BaseModel):
                payload = payload.model_dump_json(exclude_none=exclude_none)

            await self.publish(topic, payload, qos=qos, retain=retain)
        else:
            logger.warning(
                f"Cannot publish to topic {topic} – MQTT client not connected")
