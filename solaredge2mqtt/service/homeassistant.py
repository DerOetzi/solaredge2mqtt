from solaredge2mqtt.eventbus import EventBus
from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models.homeassistant import HomeAssistantDevice, HomeAssistantEntity
from solaredge2mqtt.mqtt import MQTTPublishEvent
from solaredge2mqtt.service.modbus import Modbus
from solaredge2mqtt.settings import ServiceSettings


class HomeAssistantDiscovery:
    def __init__(self, service_settings: ServiceSettings, event_bus: EventBus) -> None:
        self.settings = service_settings
        self.event_bus = event_bus

    async def publish_discovery(self) -> None:
        modbus = Modbus(self.settings.modbus)
        inv_data, meters_data, batteries_data = await modbus.loop()

        if any(data is None for data in [inv_data, meters_data, batteries_data]):
            raise InvalidDataException("Invalid modbus data")

        device_info = inv_data.homeassistant_device_info()
        logger.trace(device_info)
        device = HomeAssistantDevice(
            client_id=self.settings.mqtt.client_id,
            state_topic=f"{self.settings.mqtt.topic_prefix}/{inv_data.mqtt_topic()}",
            **device_info,
        )
        logger.debug(device)

        entities_info = inv_data.homeassistant_entities_info()
        logger.trace(entities_info)
        for entity_info in entities_info:
            entity_type = entity_info.pop("type")
            if entity_type != "sensor":
                continue

            entity = HomeAssistantEntity(
                device=device,
                **entity_info,
            )
            topic = f"{entity_type}/{entity.unique_id}/config"
            logger.debug(entity)

            await MQTTPublishEvent.emit(
                self.event_bus,
                topic=topic,
                payload=entity,
                topic_prefix=self.settings.homeassistant.topic_prefix,
                exclude_none=True,
            )
