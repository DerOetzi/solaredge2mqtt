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
from solaredge2mqtt.services.events import ComponentEvent
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType,
    HomeAssistantDevice,
    HomeAssistantEntity,
    HomeAssistantNumberType,
    HomeAssistantSensorType,
    HomeAssistantStatus,
    HomeAssistantStatusInput,
    HomeAssistantType,
)
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
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
                WallboxReadEvent,
            ],
            self.component_discovery,
        )

        self.event_bus.subscribe(
            PowerflowGeneratedEvent, self.powerflow_discovery
        )

        self.event_bus.subscribe(
            ModbusUnitsReadEvent, self.units_discovery
        )

        self.event_bus.subscribe(
            MQTTReceivedEvent,
            self.homeassistant_status,
        )

    async def async_init(self) -> None:
        await self.event_bus.emit(
            MQTTSubscribeEvent(
                self._status_topic,
                HomeAssistantStatusInput,
            )
        )

    async def component_discovery(self, event: ComponentEvent) -> None:
        publish = True
        if isinstance(event, EnergyReadEvent):
            period = event.component.info.period
            publish = (
                period.auto_discovery and (
                    event.component.mqtt_topic() not in self._seen_energy_periods
                )
            )
            self._seen_energy_periods.add(event.component.mqtt_topic())
        else:
            self.event_bus.unsubscribe(event, self.component_discovery)

        if publish:
            logger.info(
                f"Home Assistant discovery component: {event.component}")
            device_info = event.component.homeassistant_device_info()
            state_topic = self.state_topic(event.component.mqtt_topic())
            await self.publish_component(event.component, device_info, state_topic)

    async def units_discovery(self, event: ModbusUnitsReadEvent) -> None:
        self.event_bus.unsubscribe(event, self.units_discovery)
        for unit_key, unit in event.units.items():
            logger.info(f"Home Assistant discovery {unit_key}:inverter")

            device_info = unit.inverter.homeassistant_device_info()
            state_topic = self.state_topic(
                unit.inverter.mqtt_topic(self.settings.modbus.has_followers))
            await self.publish_component(unit.inverter, device_info, state_topic)

            for name, component in {**unit.meters, **unit.batteries}.items():
                logger.info(f"Home Assistant discovery {unit_key}:{name}")

                device_info = component.homeassistant_device_info_with_name(
                    name)
                state_topic = self.state_topic(
                    component.mqtt_topic(self.settings.modbus.has_followers), name)
                await self.publish_component(component, device_info, state_topic)

    async def powerflow_discovery(self, event: PowerflowGeneratedEvent) -> None:
        self.event_bus.unsubscribe(event, self.powerflow_discovery)

        for key, powerflow in event.components.items():
            logger.info(f"Home Assistant discovery {key}:powerflow")

            device_info = powerflow.homeassistant_device_info()
            state_topic = self.state_topic(powerflow.mqtt_topic())
            await self.publish_component(powerflow, device_info, state_topic)

    def state_topic(self, component_topic: str, name: str = "") -> str:
        subtopic = f"/{name.lower()}" if name else ""
        return f"{self.settings.mqtt.topic_prefix}/{component_topic}{subtopic}"

    async def publish_component(
        self,
        component: Component,
        device_info: dict[str, any],
        state_topic: str
    ) -> None:
        logger.trace(device_info)
        device = HomeAssistantDevice(
            client_id=self.settings.mqtt.client_id,
            state_topic=state_topic,
            **device_info,
        )
        logger.debug(device)

        entities_info = component.parse_schema(self.property_parser)
        for entity_info in entities_info:
            if isinstance(component, ModbusInverter):
                path = entity_info["path"]
                if (
                    not self.settings.modbus.check_grid_status
                    and path[0] == "grid_status"
                ):
                    continue

                if (
                    not self.settings.modbus.advanced_power_controls_enabled
                    and path[0] == "advanced_power_controls"
                ):
                    continue

            if (
                self.settings.is_prices_configured
                and entity_info["ha_type"] == HomeAssistantSensorType.MONETARY
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
                    retain=self.settings.homeassistant.retain,
                    topic_prefix=self.settings.homeassistant.topic_prefix,
                    exclude_none=True,
                )
            )

    async def homeassistant_status(self, event: MQTTReceivedEvent) -> None:
        if event.topic == self._status_topic:
            status = event.input.status
            if status == HomeAssistantStatus.ONLINE:
                logger.info(
                    "Home Assistant status changed to online resend discovery")
                for topic, entity in self._send_entities.items():
                    await self.event_bus.emit(
                        MQTTPublishEvent(
                            topic=topic,
                            payload=entity,
                            retain=self.settings.homeassistant.retain,
                            topic_prefix=self.settings.homeassistant.topic_prefix,
                            exclude_none=True,
                        )
                    )

    @staticmethod
    def property_parser(prop, name: str, path: list[str]) -> dict | None:
        entity: dict | None = None

        if "ha_type" in prop:
            entity = {"name": name,
                      "path": path}

            ha_type = prop["ha_type"]
            entity["icon"] = prop["icon"]

            typed = HomeAssistantType.from_string(
                prop["ha_typed"]
            )

            if typed == HomeAssistantType.BINARY_SENSOR:
                entity["ha_type"] = HomeAssistantBinarySensorType.from_string(
                    ha_type)
            elif typed == HomeAssistantType.NUMBER:
                entity["ha_type"] = HomeAssistantNumberType.from_string(
                    ha_type)
            elif typed == HomeAssistantType.SENSOR:
                entity["ha_type"] = HomeAssistantSensorType.from_string(
                    ha_type)

            for field in typed.additional_fields:
                entity[field] = prop.get(field, None)

        return entity
