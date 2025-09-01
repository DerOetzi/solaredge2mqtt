from pydantic import BaseModel

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.models import BaseInputField


class MQTTPublishEvent(BaseEvent):
    AWAIT = True

    def __init__(
        self,
        topic: str,
        payload: str | int | float | BaseModel,
        retain: bool,
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
    def __init__(self, topic: str, input: BaseInputField):
        self._topic: str = topic
        self._input: BaseInputField = input

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def input(self) -> BaseInputField:
        return self._input


class MQTTSubscribeEvent(BaseEvent):
    AWAIT = True

    def __init__(self, topic: str, model: type[BaseInputField]):
        self._topic: str = topic
        self._model: type[BaseInputField] = model

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def model(self) -> type[BaseInputField]:
        return self._model
