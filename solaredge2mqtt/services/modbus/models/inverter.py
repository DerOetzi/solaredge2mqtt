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
    HomeAssistantSelectType as HASelect,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.base import ModbusComponent
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
    storedge_control: ModbusStorEdgeControl | None = Field(default=None, title=None)

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

        if "storage_control_mode" in payload:
            values["storedge_control"] = ModbusStorEdgeControl.extract_sunspec_payload(
                payload
            )

        return values

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self.info.homeassistant_device_info("Inverter")


REMOTE_CONTROL_MODE = 4

STORAGE_CONTROL_MODE_OPTIONS = {
    0: "Disabled",
    1: "Maximize Self Consumption",
    2: "Time of Use",
    3: "Backup Only",
    4: "Remote Control",
}
STORAGE_AC_CHARGE_POLICY_OPTIONS = {
    0: "Disabled",
    1: "Always Allowed",
    2: "Fixed Energy Limit",
    3: "Percent of Production",
}
STORAGE_CHARGE_DISCHARGE_MODE_OPTIONS = {
    0: "Off",
    1: "Charge from Clipped Solar Power",
    2: "Charge from Solar Power",
    3: "Charge from Solar Power and Grid",
    4: "Discharge to Maximize Export",
    5: "Discharge to Minimize Import",
    7: "Maximize Self Consumption",
}


class ModbusStorEdgeControl(ModbusComponentValueGroup):
    storage_control_mode: int = Field(
        **HASelect.GENERIC.field(
            "Storage control mode",
            command_topic="storedge/control_mode",
            options_map=STORAGE_CONTROL_MODE_OPTIONS,
        )
    )
    storage_ac_charge_policy: int = Field(
        **HASelect.GENERIC.field(
            "AC charge policy",
            command_topic="storedge/ac_charge_policy",
            options_map=STORAGE_AC_CHARGE_POLICY_OPTIONS,
        )
    )
    storage_ac_charge_limit: float = Field(
        **HANumber.GENERIC.field(
            "AC charge limit",
            command_topic="storedge/ac_charge_limit",
            min=0,
            max=100000,
            step=1,
            mode="box",
        )
    )
    storage_backup_reserved_setting: float = Field(
        **HANumber.GENERIC.field(
            "Backup reserve",
            command_topic="storedge/backup_reserved_setting",
            unit_of_measurement="%",
            min=0,
            max=100,
            step=1,
            mode="slider",
        )
    )
    storage_default_mode: int = Field(
        **HASelect.GENERIC.field(
            "Storage default mode",
            command_topic="storedge/default_mode",
            options_map=STORAGE_CHARGE_DISCHARGE_MODE_OPTIONS,
        )
    )
    remote_control_command_timeout: int = Field(
        **HANumber.GENERIC.field(
            "Command timeout",
            command_topic="storedge/command_timeout",
            unit_of_measurement="s",
            min=0,
            max=86400,
            step=1,
            mode="box",
        )
    )
    remote_control_command_mode: int = Field(
        **HASelect.GENERIC.field(
            "Storage command mode",
            command_topic="storedge/command_mode",
            options_map=STORAGE_CHARGE_DISCHARGE_MODE_OPTIONS,
        )
    )
    remote_control_charge_limit: float = Field(
        **HANumber.GENERIC.field(
            "Charge limit",
            command_topic="storedge/charge_limit",
            device_class="power",
            unit_of_measurement="W",
            min=0,
            max=20000,
            step=1,
            mode="box",
        )
    )
    remote_control_discharge_limit: float = Field(
        **HANumber.GENERIC.field(
            "Discharge limit",
            command_topic="storedge/discharge_limit",
            device_class="power",
            unit_of_measurement="W",
            min=0,
            max=20000,
            step=1,
            mode="box",
        )
    )

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        return {
            "storage_control_mode": int(payload["storage_control_mode"]),
            "storage_ac_charge_policy": int(payload["storage_ac_charge_policy"]),
            "storage_ac_charge_limit": float(payload["storage_ac_charge_limit"]),
            "storage_backup_reserved_setting": float(
                payload["storage_backup_reserved_setting"]
            ),
            "storage_default_mode": int(payload["storage_default_mode"]),
            "remote_control_command_timeout": int(
                payload["remote_control_command_timeout"]
            ),
            "remote_control_command_mode": int(payload["remote_control_command_mode"]),
            "remote_control_charge_limit": float(
                payload["remote_control_charge_limit"]
            ),
            "remote_control_discharge_limit": float(
                payload["remote_control_discharge_limit"]
            ),
        }
