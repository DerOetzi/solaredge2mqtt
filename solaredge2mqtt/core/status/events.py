from typing import ClassVar

from solaredge2mqtt.core.events.events import BaseEvent


class ServiceOnlineEvent(BaseEvent):
    SERVICE_NAME: ClassVar[str]

    def __init__(self, debounce_cycles: int | None = None):
        self._debounce_cycles = debounce_cycles

    @property
    def debounce_cycles(self) -> int | None:
        return self._debounce_cycles


class ServiceOfflineEvent(BaseEvent):
    SERVICE_NAME: ClassVar[str]
