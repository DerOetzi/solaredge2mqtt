from solaredge2mqtt.core.status.events import ServiceOfflineEvent, ServiceOnlineEvent


class MonitoringOnlineEvent(ServiceOnlineEvent):
    SERVICE_NAME = "monitoring"


class MonitoringOfflineEvent(ServiceOfflineEvent):
    SERVICE_NAME = "monitoring"
