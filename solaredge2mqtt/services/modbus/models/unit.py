from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.modbus.models.base import ModbusUnitInfo
from solaredge2mqtt.services.modbus.models.battery import ModbusBattery
from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter
from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

if TYPE_CHECKING:
    from solaredge2mqtt.services.modbus.models.storage_control import StorageControl


class ModbusUnit(Solaredge2MQTTBaseModel):
    info: ModbusUnitInfo | None
    inverter: ModbusInverter
    meters: dict[str, ModbusMeter] = Field(default_factory=dict)
    batteries: dict[str, ModbusBattery] = Field(default_factory=dict)
    storage_control: StorageControl | None = Field(default=None)

    def has_unit_info(self) -> bool:
        return self.info is not None

    def has_storage_control(self) -> bool:
        return self.storage_control is not None and self.storage_control.is_valid
