from typing import ClassVar, TypeVar


class BaseEvent:
    AWAIT: ClassVar[bool] = False

    @classmethod
    def event_key(cls) -> str:
        return cls.__name__.lower()


TEvent = TypeVar("TEvent", bound=BaseEvent)


TEventContra = TypeVar("TEventContra", bound=BaseEvent, contravariant=True)
