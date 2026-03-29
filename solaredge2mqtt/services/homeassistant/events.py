from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.services.homeassistant.models import HomeAssistantStatusInput


class HomeAssistantStatusEvent(
    MQTTReceivedEvent[HomeAssistantStatusInput]
): ...  # pragma: no cover


class HomeAssistantSubscribeEvent(
    MQTTSubscribeEvent[HomeAssistantStatusEvent]
): ...  # pragma: no cover
