from __future__ import annotations

from typing import Any

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
from solaredge2mqtt.services.modbus.models.base import ModbusComponent
from solaredge2mqtt.services.modbus.models.inputs import ModbusPowerControlInput
from solaredge2mqtt.services.modbus.models.values import (
    ModbusAC,
    ModbusComponentValueGroup,
    ModbusDC,
)
from solaredge2mqtt.services.modbus.sunspec.values import (
    INVERTER_STATUS_MAP,
    SunSpecPayload,
)


class ModbusInverter(ModbusComponent):
    COMPONENT = "inverter"

    ac: ModbusAC = Field(title="AC")
    dc: ModbusDC = Field(title="DC")
    energytotal: float = Field(**HASensor.ENERGY_WH.field("Energy total"))
    temperature: float = Field(**HASensor.TEMP_C.field("Temperature"))
    status_text: str = Field(**HASensor.STATUS.field("Status text"))
    status: int = Field(**HASensor.STATUS.field("status"))
    grid_status: bool | None = Field(
        default=None, **HABinarySensor.GRID_STATUS.field("Grid status")
    )
    advanced_power_controls: ModbusPowerControl | None = Field(
        default=None, title="Advanced Power Controls"
    )

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        values = {
            "ac": ModbusAC.extract_sunspec_payload(payload),
            "dc": ModbusDC.extract_sunspec_payload(payload),
            "energytotal": cls.scale_value(payload, "energy_total"),
            "temperature": cls.scale_value(payload, "temperature"),
        }

        values["status"] = int(payload["status"])
        if values["status"] in INVERTER_STATUS_MAP:
            values["status_text"] = INVERTER_STATUS_MAP[values["status"]]
        else:
            values["status_text"] = "Unknown"

        if "grid_status" in payload:
            values["grid_status"] = not payload["grid_status"]

        if (
            "advanced_power_control_enable" in payload
            and payload["advanced_power_control_enable"]
        ):
            values["advanced_power_controls"] = (
                ModbusPowerControl.extract_sunspec_payload(payload)
            )

        return values

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self.info.homeassistant_device_info("Inverter")


class ModbusPowerControl(ModbusComponentValueGroup):
    advanced_power_control: bool = Field(
        **HABinarySensor.ENABLED.field("Control enabled")
    )
    active_power_limit: int = Field(
        **HANumber.ACTIVE_POWER_LIMIT.field(
            "Active PowerLimit", ModbusPowerControlInput.ACTIVE_POWER_LIMIT
        )
    )

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        return {
            "advanced_power_control": bool(payload["advanced_power_control_enable"]),
            "active_power_limit": int(payload["active_power_limit"]),
        }
