from solaredge2mqtt.services.events import ComponentEvent
from solaredge2mqtt.services.wallbox.models import WallboxAPI


class WallboxReadEvent(ComponentEvent[WallboxAPI]):
    pass
