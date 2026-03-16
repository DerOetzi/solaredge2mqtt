from typing import TypeVar


class BaseEvent:
    AWAIT = False

    @classmethod
    def event_key(cls) -> str:
        return cls.__name__.lower()


TEvent = TypeVar("TEvent", bound=BaseEvent)


TEventContra = TypeVar("TEventContra", bound=BaseEvent, contravariant=True)
