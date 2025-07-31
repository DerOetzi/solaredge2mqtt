from pydantic import Field

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.base import ModbusComponent, ModbusDeviceInfo
from solaredge2mqtt.services.modbus.models.values import (
    ModbusACCurrent,
    ModbusACPower,
    ModbusACVoltage,
    ModbusEnergy,
)


class ModbusMeter(ModbusComponent):
    COMPONENT = "meter"

    current: ModbusACCurrent = Field(title="Current")
    voltage: ModbusACVoltage = Field(title="Voltage")
    power: ModbusACPower = Field(title="Power")
    energy: ModbusEnergy = Field(title="Energy")
    frequency: float = Field(**HASensor.FREQUENCY_HZ.field("Grid frequency"))

    def __init__(self, info: ModbusDeviceInfo, data: dict[str, str | int]):
        current = ModbusACCurrent(data)
        voltage = ModbusACVoltage(data)
        power = ModbusACPower(data, "power")
        energy = ModbusEnergy(data)
        frequency = self.scale_value(data, "frequency")

        super().__init__(
            info=info,
            current=current,
            voltage=voltage,
            power=power,
            energy=energy,
            frequency=frequency,
        )

    def homeassistant_device_info_with_name(self, name: str) -> dict[str, any]:
        return self.info.homeassistant_device_info(name)
