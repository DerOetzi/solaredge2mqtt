from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent, ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole
from solaredge2mqtt.services.modbus.models.inverter import (
    REMOTE_CONTROL_MODE,
    ModbusInverter,
    ModbusStorEdgeControl,
)
from solaredge2mqtt.services.modbus.storedge_control_events import (
    StoredgeAcChargeLimitEvent,
    StoredgeAcChargeLimitSubscribeEvent,
    StoredgeAcChargePolicyEvent,
    StoredgeAcChargePolicySubscribeEvent,
    StoredgeBackupReservedSettingEvent,
    StoredgeBackupReservedSettingSubscribeEvent,
    StoredgeChargeLimitEvent,
    StoredgeChargeLimitSubscribeEvent,
    StoredgeCommandModeEvent,
    StoredgeCommandModeSubscribeEvent,
    StoredgeCommandTimeoutEvent,
    StoredgeCommandTimeoutSubscribeEvent,
    StoredgeControlModeEvent,
    StoredgeControlModeSubscribeEvent,
    StoredgeDefaultModeEvent,
    StoredgeDefaultModeSubscribeEvent,
    StoredgeDischargeLimitEvent,
    StoredgeDischargeLimitSubscribeEvent,
)
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecStorEdgeControlRegister,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import ServiceSettings

DEFAULT_UNIT_KEY = "leader"


class StorEdgeControl:
    def __init__(self, service_settings: ServiceSettings):
        self.settings = service_settings.modbus

        inverter_topic = (
            ModbusInverter.generate_topic_prefix(str(ModbusUnitRole.LEADER))
            if self.settings.has_followers
            else ModbusInverter.generate_topic_prefix()
        )
        self.topic_prefix = f"{inverter_topic}/storedge_control"

        self._last_known: dict[str, ModbusStorEdgeControl] = {}

        EventBus.register(self)

    async def async_init(self) -> None:
        if not self.settings.storedge_control_enabled:
            return

        await EventBus.emit(
            StoredgeControlModeSubscribeEvent(f"{self.topic_prefix}/control_mode")
        )
        await EventBus.emit(
            StoredgeAcChargePolicySubscribeEvent(
                f"{self.topic_prefix}/ac_charge_policy"
            )
        )
        await EventBus.emit(
            StoredgeAcChargeLimitSubscribeEvent(f"{self.topic_prefix}/ac_charge_limit")
        )
        await EventBus.emit(
            StoredgeBackupReservedSettingSubscribeEvent(
                f"{self.topic_prefix}/backup_reserved_setting"
            )
        )
        await EventBus.emit(
            StoredgeDefaultModeSubscribeEvent(f"{self.topic_prefix}/default_mode")
        )
        await EventBus.emit(
            StoredgeCommandTimeoutSubscribeEvent(f"{self.topic_prefix}/command_timeout")
        )
        await EventBus.emit(
            StoredgeCommandModeSubscribeEvent(f"{self.topic_prefix}/command_mode")
        )
        await EventBus.emit(
            StoredgeChargeLimitSubscribeEvent(f"{self.topic_prefix}/charge_limit")
        )
        await EventBus.emit(
            StoredgeDischargeLimitSubscribeEvent(f"{self.topic_prefix}/discharge_limit")
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
        force: bool = False,
    ) -> None:
        if not force and self._is_noop_write(field_name, value, unit_key):
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
        force: bool = False,
    ) -> None:
        if not force and self._is_noop_write(field_name, value, unit_key):
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

        await self._write(register, value, field_name, unit_key, force=force)

    @EventBus.subscribe(StoredgeControlModeEvent)
    async def handle_storage_control_mode(
        self, event: StoredgeControlModeEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_CONTROL_MODE,
            event.input.mode,
            "storage_control_mode",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeAcChargePolicyEvent)
    async def handle_storage_ac_charge_policy(
        self, event: StoredgeAcChargePolicyEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_AC_CHARGE_POLICY,
            event.input.policy,
            "storage_ac_charge_policy",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeAcChargeLimitEvent)
    async def handle_storage_ac_charge_limit(
        self, event: StoredgeAcChargeLimitEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_AC_CHARGE_LIMIT,
            event.input.limit,
            "storage_ac_charge_limit",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeBackupReservedSettingEvent)
    async def handle_storage_backup_reserved_setting(
        self, event: StoredgeBackupReservedSettingEvent
    ) -> None:
        await self._write(
            SunSpecStorEdgeControlRegister.STORAGE_BACKUP_RESERVED_SETTING,
            event.input.percentage,
            "storage_backup_reserved_setting",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeDefaultModeEvent)
    async def handle_storage_default_mode(
        self, event: StoredgeDefaultModeEvent
    ) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.STORAGE_DEFAULT_MODE,
            event.input.mode,
            "storage_default_mode",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeCommandTimeoutEvent)
    async def handle_command_timeout(self, event: StoredgeCommandTimeoutEvent) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_COMMAND_TIMEOUT,
            event.input.seconds,
            "remote_control_command_timeout",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeCommandModeEvent)
    async def handle_command_mode(self, event: StoredgeCommandModeEvent) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_COMMAND_MODE,
            event.input.mode,
            "remote_control_command_mode",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeChargeLimitEvent)
    async def handle_charge_limit(self, event: StoredgeChargeLimitEvent) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_CHARGE_LIMIT,
            event.input.limit,
            "remote_control_charge_limit",
            force=event.input.force,
        )

    @EventBus.subscribe(StoredgeDischargeLimitEvent)
    async def handle_discharge_limit(self, event: StoredgeDischargeLimitEvent) -> None:
        await self._write_remote_control_gated(
            SunSpecStorEdgeControlRegister.REMOTE_CONTROL_DISCHARGE_LIMIT,
            event.input.limit,
            "remote_control_discharge_limit",
            force=event.input.force,
        )
