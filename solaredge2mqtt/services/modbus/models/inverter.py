from __future__ import annotations

from pydantic import Field

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType as HABinarySensor,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantNumberType as HANumber,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.base import ModbusComponent, ModbusDeviceInfo
from solaredge2mqtt.services.modbus.models.inputs import ModbusPowerControlInput
from solaredge2mqtt.services.modbus.models.values import ModbusAC, ModbusDC
from solaredge2mqtt.services.modbus.sunspec.values import INVERTER_STATUS_MAP
from solaredge2mqtt.services.models import ComponentValueGroup


class ModbusInverter(ModbusComponent):
    COMPONENT = "inverter"

    ac: ModbusAC = Field(title="AC")
    dc: ModbusDC = Field(title="DC")
    energytotal: float = Field(**HASensor.ENERGY_WH.field("Energy total"))
    temperature: float = Field(**HASensor.TEMP_C.field("Temperature"))
    status_text: str = Field(**HASensor.STATUS.field("Status text"))
    status: int = Field(**HASensor.STATUS.field("status"))
    grid_status: bool | None = Field(
        None, **HABinarySensor.GRID_STATUS.field("Grid status")
    )
    advanced_power_controls: ModbusPowerControl | None = Field(
        None, title="Advanced Power Controls")

    def __init__(self, info: ModbusDeviceInfo, data: dict[str, str | int]):
        ac = ModbusAC(data)
        dc = ModbusDC(data)
        energytotal = self.scale_value(data, "energy_total")

        status = data["status"]
        if status in INVERTER_STATUS_MAP:
            status_text = INVERTER_STATUS_MAP[status]
        else:
            status_text = "Unknown"

        temperature = self.scale_value(data, "temperature")

        grid_status = None
        if "grid_status" in data:
            grid_status = not data["grid_status"]

        advanced_power_controls = None
        if (
            "advanced_power_control_enable" in data
            and data["advanced_power_control_enable"]
        ):
            advanced_power_controls = ModbusPowerControl(data)

        super().__init__(
            info=info,
            ac=ac,
            dc=dc,
            energytotal=energytotal,
            temperature=temperature,
            status=status,
            status_text=status_text,
            grid_status=grid_status,
            advanced_power_controls=advanced_power_controls,
        )

    def homeassistant_device_info(self) -> dict[str, any]:
        return self.info.homeassistant_device_info("Inverter")


class ModbusPowerControl(ComponentValueGroup):
    advanced_power_control: bool = Field(
        **HABinarySensor.ENABLED.field("Control enabled"))
    active_power_limit: int = Field(
        **HANumber.ACTIVE_POWER_LIMIT.field(
            ModbusPowerControlInput.ACTIVE_POWER_LIMIT,
            "Active PowerLimit"
        ))

    def __init__(self, data: dict[str, str | int | bool]):
        super().__init__(
            advanced_power_control=data["advanced_power_control_enable"],
            active_power_limit=data["active_power_limit"],
        )
