"""Storage control service for battery charge/discharge management via MQTT."""

from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.services.modbus.events import ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.models.inputs import (
    ModbusStorageChargeLimitInput,
    ModbusStorageCommandModeInput,
    ModbusStorageCommandTimeoutInput,
    ModbusStorageControlInput,
    ModbusStorageDischargeLimitInput,
)
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecStorageControlRegister,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings


class StorageControlService:
    """Service for handling battery storage control via MQTT.

    This service subscribes to MQTT topics for storage control commands
    and writes the values to the appropriate Modbus registers.

    Topics subscribed:
    - {prefix}/modbus/inverter/storage_control/charge_limit
    - {prefix}/modbus/inverter/storage_control/discharge_limit
    - {prefix}/modbus/inverter/storage_control/command_mode
    - {prefix}/modbus/inverter/storage_control/command_timeout
    """

    def __init__(self, service_settings: ServiceSettings, event_bus: EventBus):
        self.settings = service_settings.modbus
        self.mqtt_settings = service_settings.mqtt

        inverter_topic = (
            ModbusInverter.generate_topic_prefix(str(ModbusUnitRole.LEADER))
            if self.settings.has_followers
            else ModbusInverter.generate_topic_prefix()
        )

        self.topic_prefix = f"{self.mqtt_settings.topic_prefix}/{inverter_topic}"
        self.event_bus = event_bus

        self._subscribe_events()

    def _subscribe_events(self) -> None:
        if self.settings.storage_control_enabled:
            self.event_bus.subscribe(
                MQTTReceivedEvent, self._handle_mqtt_received_event
            )

    async def async_init(self) -> None:
        """Initialize the storage control service and subscribe to MQTT topics."""
        if self.settings.storage_control_enabled:
            await self._subscribe_topics()
            logger.info("Storage control service initialized")

    async def _subscribe_topics(self) -> None:
        """Subscribe to MQTT topics for storage control commands."""
        for input_field in ModbusStorageControlInput:
            topic = f"{self.topic_prefix}/storage_control/{input_field.key}"
            logger.info(f"Subscribing to storage control topic: {topic}")
            await self.event_bus.emit(
                MQTTSubscribeEvent(topic, input_field.input_model)
            )

    async def _handle_mqtt_received_event(self, event: MQTTReceivedEvent) -> None:
        """Handle incoming MQTT messages for storage control commands."""
        topic = event.topic
        input_data = event.input

        if not topic.startswith(f"{self.topic_prefix}/storage_control/"):
            return

        logger.info(f"Received storage control command on topic: {topic}")
        logger.debug(f"Storage control input: {input_data}")

        if isinstance(input_data, ModbusStorageChargeLimitInput):
            await self._write_charge_limit(input_data.limit)
        elif isinstance(input_data, ModbusStorageDischargeLimitInput):
            await self._write_discharge_limit(input_data.limit)
        elif isinstance(input_data, ModbusStorageCommandModeInput):
            await self._write_command_mode(input_data.mode)
        elif isinstance(input_data, ModbusStorageCommandTimeoutInput):
            await self._write_command_timeout(input_data.timeout)
        else:
            logger.warning(f"Unknown storage control input type: {type(input_data)}")

    async def _write_charge_limit(self, limit: float) -> None:
        """Write the charge limit to the Modbus register."""
        logger.info(f"Setting storage charge limit to {limit} W")
        await self.event_bus.emit(
            ModbusWriteEvent(SunSpecStorageControlRegister.CHARGE_LIMIT, limit)
        )

    async def _write_discharge_limit(self, limit: float) -> None:
        """Write the discharge limit to the Modbus register."""
        logger.info(f"Setting storage discharge limit to {limit} W")
        await self.event_bus.emit(
            ModbusWriteEvent(SunSpecStorageControlRegister.DISCHARGE_LIMIT, limit)
        )

    async def _write_command_mode(self, mode: int) -> None:
        """Write the command mode to the Modbus register."""
        logger.info(f"Setting storage command mode to {mode}")
        await self.event_bus.emit(
            ModbusWriteEvent(SunSpecStorageControlRegister.COMMAND_MODE, mode)
        )

    async def _write_command_timeout(self, timeout: int) -> None:
        """Write the command timeout to the Modbus register."""
        logger.info(f"Setting storage command timeout to {timeout} seconds")
        await self.event_bus.emit(
            ModbusWriteEvent(SunSpecStorageControlRegister.COMMAND_TIMEOUT, timeout)
        )
