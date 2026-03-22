from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecRawData

if TYPE_CHECKING:
    from solaredge2mqtt.services.modbus.models.unit import ModbusUnit
    from solaredge2mqtt.services.modbus.sunspec.base import SunSpecRegister
    from solaredge2mqtt.services.modbus.sunspec.values import SunSpecRawData


class ModbusUnitsReadEvent(BaseEvent):
    def __init__(self, units: dict[str, ModbusUnit]):
        self._units = units

    @property
    def units(self) -> dict[str, ModbusUnit]:
        return self._units


class ModbusWriteEvent(BaseEvent):
    AWAIT = True

    def __init__(self,
                 register: SunSpecRegister,
                 payload: SunSpecRawData):
        self._register = register
        self._payload = payload

    @property
    def register(self) -> SunSpecRegister:
        return self._register

    @property
    def payload(self) -> SunSpecRawData:
        return self._payload
