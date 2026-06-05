from solaredge2mqtt.core.status.events import ServiceOfflineEvent, ServiceOnlineEvent
from solaredge2mqtt.services.events import ComponentEvent
from solaredge2mqtt.services.wallbox.models import WallboxAPI


class WallboxReadEvent(ComponentEvent[WallboxAPI]): ...  # pragma: no cover


class WallboxOnlineEvent(ServiceOnlineEvent):
    SERVICE_NAME = "wallbox"


class WallboxOfflineEvent(ServiceOfflineEvent):
    SERVICE_NAME = "wallbox"
