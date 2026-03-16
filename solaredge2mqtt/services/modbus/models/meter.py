from typing import Any

from pydantic import Field

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.base import ModbusComponent
from solaredge2mqtt.services.modbus.models.values import (
    ModbusACCurrent,
    ModbusACPower,
    ModbusACVoltage,
    ModbusEnergy,
)
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecPayload


class ModbusMeter(ModbusComponent):
    COMPONENT = "meter"

    current: ModbusACCurrent = Field(title="Current")
    voltage: ModbusACVoltage = Field(title="Voltage")
    power: ModbusACPower = Field(title="Power")
    energy: ModbusEnergy = Field(title="Energy")
    frequency: float = Field(**HASensor.FREQUENCY_HZ.field("Grid frequency"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        return {
            "current": ModbusACCurrent.extract_sunspec_payload(payload),
            "voltage": ModbusACVoltage.extract_sunspec_payload(payload),
            "power": ModbusACPower.parse_sunspec_payload_power_key(payload, "power"),
            "energy": ModbusEnergy.extract_sunspec_payload(payload),
            "frequency": cls.scale_value(payload, "frequency"),
        }

    def homeassistant_device_info_with_name(self, name: str) -> dict[str, Any]:
        return self.info.homeassistant_device_info(name)
