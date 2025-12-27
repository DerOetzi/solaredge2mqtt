from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent
from solaredge2mqtt.services.modbus.events import ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.models.inputs import ModbusPowerControlInput
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.settings import AdvancedControlsSettings
from solaredge2mqtt.services.modbus.sunspec.inverter import SunSpecPowerControlRegister

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings


class ModbusAdvancedControl:
    def __init__(self, service_settings: ServiceSettings, event_bus: EventBus):
        self.settings = service_settings.modbus

        inverter_topic = (
            ModbusInverter.generate_topic_prefix(str(ModbusUnitRole.LEADER))
            if self.settings.has_followers
            else ModbusInverter.generate_topic_prefix())

        self.topic_prefix = f"{service_settings.mqtt.topic_prefix}/{inverter_topic}"
        self.event_bus = event_bus

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        if self.settings.advanced_power_controls_enabled:
            self.event_bus.subscribe(
                MQTTReceivedEvent, self.handle_mqtt_received_event
            )

    async def async_init(self) -> None:
        await self.handle_advanced_power_control_settings()

    async def handle_advanced_power_control_settings(self):
        if self.settings.advanced_power_controls == AdvancedControlsSettings.ENABLED:
            await self.enable_advanced_power_control()
            await self.subscribe_topics()
        elif self.settings.advanced_power_controls == AdvancedControlsSettings.DISABLE:
            await self.disable_advanced_control_settings()

            logger.warning(
                "Change setting to disabled and restart the service.")
        else:
            logger.info("Advanced power control is disabled in settings")

    def enable_advanced_power_control(self):
        logger.debug("Enabling advanced power control")
        # await self.event_bus.emit(ModbusWriteEvent(
        #    SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE, True
        # ))
        logger.info("Advanced power control enabled.")

    async def disable_advanced_control_settings(self):
        logger.debug("Disabling advanced power control")
        await self.event_bus.emit(ModbusWriteEvent(
            SunSpecPowerControlRegister.REACTIVE_POWER_CONFIG, 0
        ))

        await self.event_bus.emit(ModbusWriteEvent(
            SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE, False
        ))

        await self.event_bus.emit(ModbusWriteEvent(
            SunSpecPowerControlRegister.COMMIT_POWER_CONTROL_SETTINGS, 1
        ))

        logger.info("Advanced power control disabled.")

    def subscribe_topics(self) -> None:
        for field in ModbusInverter.parse_schema(self.property_parser):
            topic = f"{self.topic_prefix}/{field['topic']}"
            logger.info(f"Subscribing to topic: {topic}")
            # await self.event_bus.emit(MQTTSubscribeEvent(topic))

    @staticmethod
    def property_parser(
        prop: dict[str, any],
        name: str,
        path: list[str]
    ) -> dict[str, str] | None:
        field = None

        if prop.get("input_field", False):
            input_field = prop.get("input_field")
            input_field = ModbusPowerControlInput.from_string(input_field)
            field = {
                "name": name,
                "topic": "/".join(path),
                "input_field": input_field,
            }

        return field

    def handle_mqtt_received_event(self, event: MQTTReceivedEvent) -> None:
        logger.info(event.input)
