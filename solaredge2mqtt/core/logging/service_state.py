from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.logging.models import ServiceStateEnum
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent

if TYPE_CHECKING:
    from solaredge2mqtt.core.events import EventBus


class ServiceStateMixin:
    """Mixin that adds subservice state tracking and MQTT state reporting."""

    SERVICE_STATE_NAME: ClassVar[str]

    def _init_service_state(self) -> None:
        self._service_state: ServiceStateEnum = ServiceStateEnum.UNKNOWN

    @property
    def service_state(self) -> ServiceStateEnum:
        return self._service_state

    async def _set_service_state(
        self, state: ServiceStateEnum, event_bus: EventBus
    ) -> None:
        if not hasattr(self, "_service_state") or self._service_state != state:
            self._service_state = state
            logger.debug(
                "Service state changed: {name} -> {state}",
                name=self.SERVICE_STATE_NAME,
                state=state.value,
            )
            await event_bus.emit(
                MQTTPublishEvent(
                    f"status/{self.SERVICE_STATE_NAME}",
                    state.value,
                    retain=True,
                )
            )
