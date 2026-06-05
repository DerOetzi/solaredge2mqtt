from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.core.status.events import ServiceOfflineEvent, ServiceOnlineEvent


class InfluxDBAggregatedEvent(BaseEvent): ...  # pragma: no cover


class InfluxDBOnlineEvent(ServiceOnlineEvent):
    SERVICE_NAME = "influxdb"


class InfluxDBOfflineEvent(ServiceOfflineEvent):
    SERVICE_NAME = "influxdb"
