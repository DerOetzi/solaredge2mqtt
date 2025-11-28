from pydantic import Field

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantNumberType as HANumber,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.inputs import ModbusStorageControlInput
from solaredge2mqtt.services.modbus.sunspec.values import (
    STORAGE_AC_CHARGE_POLICY_MAP,
    STORAGE_COMMAND_MODE_MAP,
    STORAGE_CONTROL_MODE_MAP,
)
from solaredge2mqtt.services.models import ComponentValueGroup


class ModbusStorageControl(ComponentValueGroup):
    """Model for battery storage control data read from Modbus registers."""

    control_mode: int = Field(**HASensor.STATUS.field("Control mode"))
    control_mode_text: str = Field(**HASensor.STATUS.field("Control mode text"))
    ac_charge_policy: int = Field(**HASensor.STATUS.field("AC charge policy"))
    ac_charge_policy_text: str = Field(
        **HASensor.STATUS.field("AC charge policy text"))
    ac_charge_limit: float = Field(**HASensor.ENERGY_WH.field("AC charge limit"))
    backup_reserve: float = Field(**HASensor.BATTERY.field("Backup reserve"))
    default_mode: int = Field(**HASensor.STATUS.field("Default mode"))
    default_mode_text: str = Field(**HASensor.STATUS.field("Default mode text"))
    command_timeout: int = Field(**HASensor.DURATION_S.field("Command timeout"))
    command_mode: int = Field(
        **HANumber.STORAGE_COMMAND_TIMEOUT.field(
            ModbusStorageControlInput.COMMAND_MODE,
            "Command mode"
        ))
    command_mode_text: str = Field(**HASensor.STATUS.field("Command mode text"))
    charge_limit: float = Field(
        **HANumber.STORAGE_CHARGE_LIMIT.field(
            ModbusStorageControlInput.CHARGE_LIMIT,
            "Charge limit"
        ))
    discharge_limit: float = Field(
        **HANumber.STORAGE_DISCHARGE_LIMIT.field(
            ModbusStorageControlInput.DISCHARGE_LIMIT,
            "Discharge limit"
        ))

    def __init__(self, data: dict[str, str | int | float]) -> None:
        control_mode = int(data.get("storage_control_mode", 0))
        control_mode_text = STORAGE_CONTROL_MODE_MAP.get(control_mode, "Unknown")

        ac_charge_policy = int(data.get("storage_ac_charge_policy", 0))
        ac_charge_policy_text = STORAGE_AC_CHARGE_POLICY_MAP.get(
            ac_charge_policy, "Unknown")

        ac_charge_limit = float(data.get("storage_ac_charge_limit", 0))
        backup_reserve = float(data.get("storage_backup_reserve", 0))

        default_mode = int(data.get("storage_default_mode", 0))
        default_mode_text = STORAGE_COMMAND_MODE_MAP.get(default_mode, "Unknown")

        command_timeout = int(data.get("storage_command_timeout", 0))

        command_mode = int(data.get("storage_command_mode", 0))
        command_mode_text = STORAGE_COMMAND_MODE_MAP.get(command_mode, "Unknown")

        charge_limit = float(data.get("storage_charge_limit", 0))
        discharge_limit = float(data.get("storage_discharge_limit", 0))

        super().__init__(
            control_mode=control_mode,
            control_mode_text=control_mode_text,
            ac_charge_policy=ac_charge_policy,
            ac_charge_policy_text=ac_charge_policy_text,
            ac_charge_limit=ac_charge_limit,
            backup_reserve=backup_reserve,
            default_mode=default_mode,
            default_mode_text=default_mode_text,
            command_timeout=command_timeout,
            command_mode=command_mode,
            command_mode_text=command_mode_text,
            charge_limit=charge_limit,
            discharge_limit=discharge_limit,
        )

    @property
    def is_remote_control_enabled(self) -> bool:
        """Check if the storage is in remote control mode (mode 4)."""
        return self.control_mode == 4

    @property
    def is_valid(self) -> bool:
        """Check if the storage control data is valid."""
        valid = True

        if self.charge_limit < 0:
            logger.warning("Storage charge limit is negative")
            valid = False
        elif self.discharge_limit < 0:
            logger.warning("Storage discharge limit is negative")
            valid = False
        elif self.backup_reserve < 0 or self.backup_reserve > 100:
            logger.warning("Storage backup reserve out of range")
            valid = False

        return valid
