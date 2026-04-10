from functools import cache
from typing import Generic, TypeVar, get_args

from pydantic import BaseModel

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.models import TBaseInputField


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


class MQTTReceivedEvent(Generic[TBaseInputField], BaseEvent):
    def __init__(self, topic: str, input: TBaseInputField):
        self._topic: str = topic
        self._input: TBaseInputField = input

    @property
    def topic(self) -> str:
        return self._topic

    @property
    def input(self) -> TBaseInputField:
        return self._input

    @classmethod
    @cache
    def input_model(cls) -> type[TBaseInputField]:
        for base in getattr(cls, "__orig_bases__", []):
            args = get_args(base)
            if args:
                return args[0]
        raise TypeError(
            f"{cls.__name__} must specify a generic input model "
            "for MQTTReceivedEvent[TBaseInputField]"
        )


TMQTTReceivedEvent = TypeVar("TMQTTReceivedEvent", bound=MQTTReceivedEvent)


class MQTTSubscribeEvent(Generic[TMQTTReceivedEvent], BaseEvent):
    AWAIT = True

    def __init__(self, topic: str):
        self._topic: str = topic

    @property
    def topic(self) -> str:
        return self._topic

    @classmethod
    @cache
    def event(cls) -> type[TMQTTReceivedEvent]:
        for base in getattr(cls, "__orig_bases__", []):
            args = get_args(base)
            if args:
                return args[0]
        raise TypeError(
            f"{cls.__name__} must specify a generic received event "
            "for MQTTSubscribeEvent[TMQTTReceivedEvent]"
        )
