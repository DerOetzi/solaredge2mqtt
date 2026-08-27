from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.status.events import ServiceOfflineEvent, ServiceOnlineEvent


class StorageAggregatedEvent(BaseEvent): ...  # pragma: no cover


class StorageOnlineEvent(ServiceOnlineEvent):
    SERVICE_NAME = "storage"


class StorageOfflineEvent(ServiceOfflineEvent):
    SERVICE_NAME = "storage"
