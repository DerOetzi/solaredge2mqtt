from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import (
    MQTTReceivedEvent,
    MQTTSubscribeEvent,
)
from solaredge2mqtt.services.modbus.events import ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.models.inputs import (
    ModbusPowerControlInput,
    ModbusStorageControlInput,
)
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.models.storage_control import StorageControl
from solaredge2mqtt.services.modbus.settings import AdvancedControlsSettings
from solaredge2mqtt.services.modbus.sunspec.battery import SunSpecStorageControlRegister
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


class ModbusStorageControl:
    """Handler for storage control commands via MQTT.

    This class manages MQTT subscriptions for battery storage control commands
    and writes the received values to the appropriate modbus registers.
    """

    def __init__(self, service_settings: ServiceSettings, event_bus: EventBus):
        self.settings = service_settings.modbus
        self.mqtt_settings = service_settings.mqtt

        storage_control_topic = (
            StorageControl.generate_topic_prefix(str(ModbusUnitRole.LEADER))
            if self.settings.has_followers
            else StorageControl.generate_topic_prefix()
        )

        self.topic_prefix = f"{self.mqtt_settings.topic_prefix}/{storage_control_topic}"
        self.event_bus = event_bus
        self._subscribed_topics: dict[str, ModbusStorageControlInput] = {}

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        if self.settings.storage_control_enabled:
            self.event_bus.subscribe(
                MQTTReceivedEvent, self._handle_mqtt_received_event
            )

    async def async_init(self) -> None:
        """Initialize storage control and subscribe to MQTT topics."""
        if self.settings.storage_control_enabled:
            logger.warning(
                "Storage Control is enabled. Use at your own risk! "
                "Adjustable parameters in Modbus registers are intended for "
                "long-term storage. Periodic changes may damage the flash memory."
            )
            await self._subscribe_topics()
        else:
            logger.info("Storage control is disabled in settings")

    async def _subscribe_topics(self) -> None:
        """Subscribe to all storage control MQTT topics.

        Iterates through ModbusStorageControlInput enum to subscribe to
        all available storage control command topics.
        """
        for input_type in ModbusStorageControlInput:
            topic = f"{self.topic_prefix}/{input_type.key}/set"
            logger.info(f"Subscribing to storage control topic: {topic}")
            self._subscribed_topics[topic] = input_type
            await self.event_bus.emit(MQTTSubscribeEvent(topic, input_type.input_model))

    async def _handle_mqtt_received_event(self, event: MQTTReceivedEvent) -> None:
        """Handle incoming MQTT messages for storage control."""
        topic = event.topic

        if topic not in self._subscribed_topics:
            return

        input_type = self._subscribed_topics[topic]
        input_data = event.input

        logger.info(
            f"Received storage control command: {input_type.key} = {input_data}"
        )

        try:
            await self._write_storage_control(input_type, input_data)
        except (ValueError, TypeError) as e:
            logger.error(f"Error processing storage control command: {e}")

    async def _write_storage_control(
        self, input_type: ModbusStorageControlInput, input_data
    ) -> None:
        """Write storage control value to modbus register."""
        register = None
        value = None

        if input_type == ModbusStorageControlInput.CONTROL_MODE:
            register = SunSpecStorageControlRegister.CONTROL_MODE
            value = input_data.mode
        elif input_type == ModbusStorageControlInput.DEFAULT_MODE:
            register = SunSpecStorageControlRegister.DEFAULT_MODE
            value = input_data.mode
        elif input_type == ModbusStorageControlInput.CHARGE_LIMIT:
            register = SunSpecStorageControlRegister.CHARGE_LIMIT
            value = float(input_data.limit)
        elif input_type == ModbusStorageControlInput.DISCHARGE_LIMIT:
            register = SunSpecStorageControlRegister.DISCHARGE_LIMIT
            value = float(input_data.limit)
        elif input_type == ModbusStorageControlInput.BACKUP_RESERVE:
            register = SunSpecStorageControlRegister.BACKUP_RESERVE
            value = float(input_data.percent)
        elif input_type == ModbusStorageControlInput.COMMAND_TIMEOUT:
            register = SunSpecStorageControlRegister.COMMAND_TIMEOUT
            value = input_data.seconds

        if register is not None and value is not None:
            logger.info(
                f"Writing storage control: {register.identifier} = {value}"
            )
            await self.event_bus.emit(ModbusWriteEvent(register, value))
