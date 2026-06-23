from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.core.status.events import ServiceOfflineEvent, ServiceOnlineEvent
from solaredge2mqtt.services.events import ComponentEvent
from solaredge2mqtt.services.monitoring.inputs import EVChargerChargeLevelInput
from solaredge2mqtt.services.monitoring.models import EVCharger


class MonitoringOnlineEvent(ServiceOnlineEvent):
    SERVICE_NAME = "monitoring"


class MonitoringOfflineEvent(ServiceOfflineEvent):
    SERVICE_NAME = "monitoring"


class EVChargerReadEvent(ComponentEvent[EVCharger]): ...  # pragma: no cover


class EVChargerChargeLevelEvent(
    MQTTReceivedEvent[EVChargerChargeLevelInput]
): ...  # pragma: no cover


class EVChargerChargeLevelSubscribeEvent(
    MQTTSubscribeEvent[EVChargerChargeLevelEvent]
): ...  # pragma: no cover
