from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent, ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.models.inverter import (
    ModbusInverter,
    ModbusStorEdgeControl,
)
from solaredge2mqtt.services.modbus.storedge_control_events import (
    RemoteControlChargeLimitEvent,
    RemoteControlChargeLimitSubscribeEvent,
    RemoteControlCommandModeEvent,
    RemoteControlCommandModeSubscribeEvent,
    RemoteControlCommandTimeoutEvent,
    RemoteControlCommandTimeoutSubscribeEvent,
    RemoteControlDischargeLimitEvent,
    RemoteControlDischargeLimitSubscribeEvent,
    StorageAcChargeLimitEvent,
    StorageAcChargeLimitSubscribeEvent,
    StorageAcChargePolicyEvent,
    StorageAcChargePolicySubscribeEvent,
    StorageBackupReservedSettingEvent,
    StorageBackupReservedSettingSubscribeEvent,
    StorageControlModeEvent,
    StorageControlModeSubscribeEvent,
    StorageDefaultModeEvent,
    StorageDefaultModeSubscribeEvent,
)
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecStorEdgeControlRegister,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings

REMOTE_CONTROL_MODE = 4
DEFAULT_UNIT_KEY = "leader"


class StorEdgeControl:
    def __init__(self, service_settings: ServiceSettings):
        self.settings = service_settings.modbus

        inverter_topic = (
            ModbusInverter.generate_topic_prefix(str(ModbusUnitRole.LEADER))
            if self.settings.has_followers
            else ModbusInverter.generate_topic_prefix()
        )
        # The MQTT client prepends its own topic_prefix in _subscribe_topic,
        # so this must stay relative (no service_settings.mqtt.topic_prefix here).
        self.topic_prefix = f"{inverter_topic}/storedge_control"

        self._last_known: dict[str, ModbusStorEdgeControl] = {}

        EventBus.register(self)

    async def async_init(self) -> None:
        if not self.settings.storedge_control_enabled:
            return

        await EventBus.emit(
            StorageControlModeSubscribeEvent(
                f"{self.topic_prefix}/storage_control_mode"
            )
        )
        await EventBus.emit(
            StorageAcChargePolicySubscribeEvent(
                f"{self.topic_prefix}/storage_ac_charge_policy"
            )
        )
        await EventBus.emit(
            StorageAcChargeLimitSubscribeEvent(
                f"{self.topic_prefix}/storage_ac_charge_limit"
            )
        )
        await EventBus.emit(
            StorageBackupReservedSettingSubscribeEvent(
                f"{self.topic_prefix}/storage_backup_reserved_setting"
            )
        )
        await EventBus.emit(
            StorageDefaultModeSubscribeEvent(
                f"{self.topic_prefix}/storage_default_mode"
            )
        )
        await EventBus.emit(
            RemoteControlCommandTimeoutSubscribeEvent(
                f"{self.topic_prefix}/remote_control_command_timeout"
            )
        )
        await EventBus.emit(
            RemoteControlCommandModeSubscribeEvent(
                f"{self.topic_prefix}/remote_control_command_mode"
            )
        )
        await EventBus.emit(
            RemoteControlChargeLimitSubscribeEvent(
                f"{self.topic_prefix}/remote_control_charge_limit"
            )
        )
        await EventBus.emit(
            RemoteControlDischargeLimitSubscribeEvent(
                f"{self.topic_prefix}/remote_control_discharge_limit"
            )
        )

    @EventBus.subscribe(ModbusUnitsReadEvent)
    async def cache_storedge_control(self, event: ModbusUnitsReadEvent) -> None:
        for unit_key, unit in event.units.items():
            if unit.inverter.storedge_control is not None:
                self._last_known[unit_key] = unit.inverter.storedge_control

    def _is_remote_control_active(self, unit_key: str = DEFAULT_UNIT_KEY) -> bool:
        last = self._last_known.get(unit_key)
        return last is not None and last.storage_control_mode == REMOTE_CONTROL_MODE

    def _is_noop_write(
        self, field_name: str, value: int | float, unit_key: str
    ) -> bool:
        last = self._last_known.get(unit_key)
        return last is not None and getattr(last, field_name) == value

    async def _write(
        self,
        register: SunSpecStorEdgeControlRegister,
        value: int | float,
        field_name: str,
        unit_key: str = DEFAULT_UNIT_KEY,
    ) -> None:
        if self._is_noop_write(field_name, value, unit_key):
            logger.debug(
                "Skipping StorEdge control {field}: {value} already active "
                "on unit {unit_key}",
                field=field_name,
                value=value,
                unit_key=unit_key,
            )
            return

        logger.info(
            "Writing StorEdge control {field}: {value} (unit {unit_key})",
            field=field_name,
            value=value,
            unit_key=unit_key,
        )
        await EventBus.emit(ModbusWriteEvent(register, value, unit_key=unit_key))

    async def _write_remote_control_gated(
        self,
        register: SunSpecStorEdgeControlRegister,
        value: int | float,
        field_name: str,
        unit_key: str = DEFAULT_UNIT_KEY,
    ) -> None:
        if self._is_noop_write(field_name, value, unit_key):
            logger.debug(
                "Skipping StorEdge control {field}: {value} already active "
                "on unit {unit_key}",
                field=field_name,
                value=value,
                unit_key=unit_key,
            )
            return

        if not self._is_remote_control_active(unit_key):
            logger.error(
                "Cannot write StorEdge control {field}: Storage Control Mode is not "
                "set to Remote Control on unit {unit_key}. "
                "Set storage_control_mode to 4 first.",
                field=field_name,
                unit_key=unit_key,
            )
            return

        await self._write(register, value, field_name, unit_key)

    @EventBus.subscribe(StorageControlModeEvent)
    async def handle_storage_control_mode(self, event: StorageControlModeEvent) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_CONTROL_MODE,
            event.input.mode,
            "storage_control_mode",
        )

    @EventBus.subscribe(StorageAcChargePolicyEvent)
    async def handle_storage_ac_charge_policy(
        self, event: StorageAcChargePolicyEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_AC_CHARGE_POLICY,
            event.input.policy,
            "storage_ac_charge_policy",
        )

    @EventBus.subscribe(StorageAcChargeLimitEvent)
    async def handle_storage_ac_charge_limit(
        self, event: StorageAcChargeLimitEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_AC_CHARGE_LIMIT,
            event.input.limit,
            "storage_ac_charge_limit",
        )

    @EventBus.subscribe(StorageBackupReservedSettingEvent)
    async def handle_storage_backup_reserved_setting(
        self, event: StorageBackupReservedSettingEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_BACKUP_RESERVED_SETTING,
            event.input.percentage,
            "storage_backup_reserved_setting",
        )

    @EventBus.subscribe(StorageDefaultModeEvent)
    async def handle_storage_default_mode(self, event: StorageDefaultModeEvent) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.STORAGE_DEFAULT_MODE,
            event.input.mode,
            "storage_default_mode",
        )

    @EventBus.subscribe(RemoteControlCommandTimeoutEvent)
    async def handle_remote_control_command_timeout(
        self, event: RemoteControlCommandTimeoutEvent
    ) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_COMMAND_TIMEOUT,
            event.input.seconds,
            "remote_control_command_timeout",
        )

    @EventBus.subscribe(RemoteControlCommandModeEvent)
    async def handle_remote_control_command_mode(
        self, event: RemoteControlCommandModeEvent
    ) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_COMMAND_MODE,
            event.input.mode,
            "remote_control_command_mode",
        )

    @EventBus.subscribe(RemoteControlChargeLimitEvent)
    async def handle_remote_control_charge_limit(
        self, event: RemoteControlChargeLimitEvent
    ) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_CHARGE_LIMIT,
            event.input.limit,
            "remote_control_charge_limit",
        )

    @EventBus.subscribe(RemoteControlDischargeLimitEvent)
    async def handle_remote_control_discharge_limit(
        self, event: RemoteControlDischargeLimitEvent
    ) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_DISCHARGE_LIMIT,
            event.input.limit,
            "remote_control_discharge_limit",
        )
