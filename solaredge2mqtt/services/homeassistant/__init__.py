from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import (
    MQTTPublishEvent,
    MQTTReceivedEvent,
    MQTTSubscribeEvent,
)
from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.events import ComponentEvent, ComponentsEvent
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantDevice,
    HomeAssistantEntity,
    HomeAssistantEntityType,
)
from solaredge2mqtt.services.modbus.events import (
    ModbusBatteriesReadEvent,
    ModbusInverterReadEvent,
    ModbusMetersReadEvent,
)
from solaredge2mqtt.services.models import Component
from solaredge2mqtt.services.powerflow.events import PowerflowGeneratedEvent
from solaredge2mqtt.services.wallbox.events import WallboxReadEvent

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings import ServiceSettings


class HomeAssistantDiscovery:
    def __init__(self, service_settings: ServiceSettings, event_bus: EventBus) -> None:
        self.settings = service_settings
        self._send_entities: dict[str, HomeAssistantEntity] = {}
        logger.info("Home Assistant discovery enabled")

        self._status_topic = f"{self.settings.homeassistant.topic_prefix}/status"

        self._seen_energy_periods: set[str] = set()

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(
            [
                ForecastEvent,
                EnergyReadEvent,
                ModbusInverterReadEvent,
                PowerflowGeneratedEvent,
                WallboxReadEvent,
            ],
            self.component_discovery,
        )

        self.event_bus.subscribe(
            [ModbusMetersReadEvent, ModbusBatteriesReadEvent], self.components_discovery
        )

        self.event_bus.subscribe(
            MQTTReceivedEvent,
            self.homeassistant_status,
        )

    async def async_init(self) -> None:
        await self.event_bus.emit(MQTTSubscribeEvent(self._status_topic))

    async def component_discovery(self, event: ComponentEvent) -> None:
        publish = True
        if isinstance(event, EnergyReadEvent):
            period = event.component.info.period
            publish = (
                period.auto_discovery and period.topic not in self._seen_energy_periods
            )
            self._seen_energy_periods.add(period.topic)
        else:
            self.event_bus.unsubscribe(event, self.component_discovery)

        if publish:
            logger.info(f"Home Assistant discovery component: {event.component}")
            await self.publish_component(event.component)

    async def components_discovery(self, event: ComponentsEvent) -> None:
        self.event_bus.unsubscribe(event, self.components_discovery)
        for name, component in event.components.items():
            logger.info(f"Home Assistant discovery component: {component}")
            await self.publish_component(component, name)

    async def publish_component(self, component: Component, name: str = "") -> None:
        subtopic = f"/{name.lower()}" if name else ""

        state_topic = (
            f"{self.settings.mqtt.topic_prefix}/{component.mqtt_topic()}{subtopic}"
        )

        if name:
            device_info = component.homeassistant_device_info_with_name(name)
        else:
            device_info = component.homeassistant_device_info()

        logger.trace(device_info)
        device = HomeAssistantDevice(
            client_id=self.settings.mqtt.client_id,
            state_topic=state_topic,
            **device_info,
        )
        logger.debug(device)

        entities_info = component.homeassistant_entities_info()
        for entity_info in entities_info:
            if self.settings.is_prices_configured and entity_info["ha_type"] == str(
                HomeAssistantEntityType.MONETARY
            ):
                entity_info["unit"] = self.settings.prices.currency

            entity = HomeAssistantEntity(
                device=device,
                **entity_info,
            )
            topic = (
                f"{entity.ha_type.typed}/"
                f"{state_topic.replace('/', '_')}/"
                f"{entity.unique_id}/config"
            )
            logger.debug(entity)

            self._send_entities[topic] = entity

            await self.event_bus.emit(
                MQTTPublishEvent(
                    topic=topic,
                    payload=entity,
                    topic_prefix=self.settings.homeassistant.topic_prefix,
                    exclude_none=True,
                )
            )

    async def homeassistant_status(self, event: MQTTReceivedEvent) -> None:
        if event.topic == self._status_topic and event.payload == "online":
            logger.info("Home Assistant status changed to online resend discovery")
            for topic, entity in self._send_entities.items():
                await self.event_bus.emit(
                    MQTTPublishEvent(
                        topic=topic,
                        payload=entity,
                        topic_prefix=self.settings.homeassistant.topic_prefix,
                        exclude_none=True,
                    )
                )
