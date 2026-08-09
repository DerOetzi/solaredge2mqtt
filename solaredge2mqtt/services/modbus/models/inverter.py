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
    storedge_control: ModbusStorEdgeControl | None = Field(
        default=None, title="StorEdge Control"
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

        if "storage_control_mode" in payload:
            values["storedge_control"] = ModbusStorEdgeControl.extract_sunspec_payload(
                payload
            )

        return values

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self.info.homeassistant_device_info("Inverter")


REMOTE_CONTROL_MODE = 4


class ModbusStorEdgeControl(ModbusComponentValueGroup):
    storage_control_mode: int = Field(
        **HASelect.STOREDGE_CONTROL_MODE.field(
            "Storage control mode", command_topic="storedge/control_mode"
        )
    )
    storage_ac_charge_policy: int = Field(
        **HASelect.STOREDGE_AC_CHARGE_POLICY.field(
            "Storage AC charge policy", command_topic="storedge/ac_charge_policy"
        )
    )
    storage_ac_charge_limit: float = Field(
        **HANumber.STOREDGE_AC_CHARGE_LIMIT.field(
            "Storage AC charge limit", command_topic="storedge/ac_charge_limit"
        )
    )
    storage_backup_reserved_setting: float = Field(
        **HANumber.STOREDGE_BACKUP_RESERVED.field(
            "Storage backup reserved setting",
            command_topic="storedge/backup_reserved_setting",
        )
    )
    storage_default_mode: int = Field(
        **HASelect.STOREDGE_CHARGE_DISCHARGE_MODE.field(
            "Storage default mode (Remote Control mode only)",
            command_topic="storedge/default_mode",
        )
    )
    remote_control_command_timeout: int = Field(
        **HANumber.STOREDGE_COMMAND_TIMEOUT.field(
            "Remote control command timeout (Remote Control mode only)",
            command_topic="storedge/command_timeout",
        )
    )
    remote_control_command_mode: int = Field(
        **HASelect.STOREDGE_CHARGE_DISCHARGE_MODE.field(
            "Remote control command mode (Remote Control mode only)",
            command_topic="storedge/command_mode",
        )
    )
    remote_control_charge_limit: float = Field(
        **HANumber.STOREDGE_CHARGE_LIMIT.field(
            "Remote control charge limit (Remote Control mode only)",
            command_topic="storedge/charge_limit",
        )
    )
    remote_control_discharge_limit: float = Field(
        **HANumber.STOREDGE_DISCHARGE_LIMIT.field(
            "Remote control discharge limit (Remote Control mode only)",
            command_topic="storedge/discharge_limit",
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
