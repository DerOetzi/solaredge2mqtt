import json

from pydantic import BaseModel

from solaredge2mqtt.core.events.events import BaseEvent


class MQTTPublishEvent(BaseEvent):
    AWAIT = True

    def __init__(
        self,
        topic: str,
        payload: str | int | float | BaseModel,
        retain: bool = False,
        qos: int = 0,
        topic_prefix: str | None = None,
        exclude_none: bool = False,
    ):
        self._topic: str = topic
        self._payload: str | int | float | BaseModel = payload
        self._retain: bool = retain
        self._qos: int = qos
        self._topic_prefix: str | None = topic_prefix
        self._exclude_none: bool = exclude_none

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def payload(self) -> str | int | float | BaseModel:
        return self._payload

    @property
    def retain(self) -> bool:
        return self._retain

    @property
    def qos(self) -> int:
        return self._qos

    @property
    def topic_prefix(self) -> str | None:
        return self._topic_prefix

    @property
    def exclude_none(self) -> bool:
        return self._exclude_none


class MQTTReceivedEvent(BaseEvent):
    def __init__(self, topic: str, payload: str):
        self._topic: str = topic
        self._payload: str = payload

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def payload(self) -> str:
        return self._payload

    @property
    def json(self) -> dict | str | int | float:
        return json.loads(self.payload)


class MQTTSubscribeEvent(BaseEvent):
    AWAIT = True

    def __init__(self, topic: str):
        self._topic: str = topic

    @property
    def topic(self) -> str:
        return self._topic
