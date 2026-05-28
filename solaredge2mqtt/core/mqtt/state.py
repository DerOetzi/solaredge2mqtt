from __future__ import annotations

from enum import StrEnum

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent


class ServiceState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class ServiceStateController:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self._state: ServiceState | None = None

    async def set_online(self) -> None:
        await self._set_state(ServiceState.ONLINE)

    async def set_offline(self) -> None:
        await self._set_state(ServiceState.OFFLINE)

    async def _set_state(self, state: ServiceState) -> None:
        if self._state == state:
            return

        self._state = state
        await EventBus.emit(
            MQTTPublishEvent(f"status/{self.service_name}", state.value, True)
        )
