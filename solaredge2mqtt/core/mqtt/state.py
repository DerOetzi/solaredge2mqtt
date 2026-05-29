from __future__ import annotations

from enum import StrEnum

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent


class ServiceState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"


class ServiceStateController:
    """Publish service online/offline state with optional transition debouncing."""

    def __init__(self, service_name: str, debounce_cycles: int = 0) -> None:
        self.service_name = service_name
        self.debounce_cycles = max(0, debounce_cycles)
        self._state: ServiceState | None = None
        self._pending_state: ServiceState | None = None
        self._pending_count = 0

    async def set_online(self) -> None:
        await self._set_state(ServiceState.ONLINE)

    async def set_offline(self) -> None:
        await self._set_state(ServiceState.OFFLINE)

    async def _set_state(self, state: ServiceState) -> None:
        """Apply debounce rules and publish state only after stable transitions."""
        if self._state == state:
            self._pending_state = None
            self._pending_count = 0
            return

        if self._state is None:
            await self._publish_state(state)
            return

        if self.debounce_cycles <= 1:
            await self._publish_state(state)
            return

        if self._pending_state != state:
            self._pending_state = state
            self._pending_count = 1
            return

        self._pending_count += 1
        if self._pending_count < self.debounce_cycles:
            return

        await self._publish_state(state)

    async def _publish_state(self, state: ServiceState) -> None:
        self._state = state
        self._pending_state = None
        self._pending_count = 0
        await EventBus.emit(
            MQTTPublishEvent(
                f"status/{self.service_name}",
                state.value,
                False,
                suppress_connection_error=True
            )
        )
