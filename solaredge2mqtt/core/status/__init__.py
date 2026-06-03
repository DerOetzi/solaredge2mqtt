from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.status.events import (
    ServiceOfflineEvent,
    ServiceOnlineEvent,
)


class ServiceStatusController:
    def __init__(self):
        self._configurations: dict[str, int] = {}
        self._status: dict[str, bool] = {}
        self._pending_status_changes: dict[str, bool] = {}
        self._debounce_counters: dict[str, int] = {}

        EventBus.register(self)

    async def online(self):
        await EventBus.emit(
            MQTTPublishEvent(
                "status",
                "online",
                True,
                suppress_connection_error=True
            )
        )

        for service_name, is_online in self._status.items():
            await self._publish_service_status(service_name, is_online)

    async def offline(self):
        await EventBus.emit(
            MQTTPublishEvent(
                "status",
                "offline",
                True,
                suppress_connection_error=True
            )
        )

        for service_name in self._status.keys():
            await self._publish_service_status(service_name, False)

    @EventBus.subscribe(ServiceOnlineEvent)
    async def handle_online(self, event: ServiceOnlineEvent):
        service_name = event.SERVICE_NAME
        debounce_cycles = event.debounce_cycles

        if service_name not in self._configurations and debounce_cycles is not None:
            self._configurations[service_name] = debounce_cycles
            self._debounce_counters[service_name] = 0

        if service_name not in self._configurations:
            logger.warning(
                f"Received status update for unconfigured service: {service_name}")
            return

        await self._update_service_status(service_name, True)

    @EventBus.subscribe(ServiceOfflineEvent)
    async def handle_offline(self, event: ServiceOfflineEvent):
        service_name = event.SERVICE_NAME
        if service_name not in self._configurations:
            return

        await self._update_service_status(service_name, False)

    async def _update_service_status(self, service_name: str, is_online: bool):
        current_status = self._status.get(service_name, None)
        debounce_cycles = self._configurations.get(service_name, 0)
        if debounce_cycles <= 1 or current_status is None:
            await self._publish_service_status(service_name, is_online)
            return

        if current_status != is_online:
            pending_status = self._pending_status_changes.get(
                service_name, None)
            if pending_status is None:
                self._pending_status_changes[service_name] = is_online
                self._debounce_counters[service_name] = 1
            else:
                self._debounce_counters[service_name] += 1

            if self._debounce_counters[service_name] >= debounce_cycles:
                await self._publish_service_status(service_name, is_online)
            else:
                return

        self._reset_debounce(service_name)

    async def _publish_service_status(self, service_name: str, is_online: bool):
        self._status[service_name] = is_online
        self._reset_debounce(service_name)
        await EventBus.emit(
            MQTTPublishEvent(
                f"status/{service_name}",
                "online" if is_online else "offline",
                False,
                suppress_connection_error=True
            )
        )

    def _reset_debounce(self, service_name):
        self._pending_status_changes.pop(service_name, None)
        self._debounce_counters[service_name] = 0
