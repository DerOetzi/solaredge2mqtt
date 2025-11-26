from pydantic import Field, field_validator

from solaredge2mqtt.core.models import BaseInputField, BaseInputFieldEnumModel


class ModbusActivePowerLimitInput(BaseInputField):
    limit: int = Field(ge=0, le=100)


class ModbusPowerControlInput(BaseInputFieldEnumModel):
    ACTIVE_POWER_LIMIT = "active_power_limit", ModbusActivePowerLimitInput


class StorageControlModeInput(BaseInputField):
    """Input model for storage control mode.

    Control mode values:
        0: Disabled
        1: Maximize Self Consumption
        2: Time of Use
        3: Backup Only
        4: Remote Control
    """

    mode: int = Field(ge=0, le=4)


class StorageDefaultModeInput(BaseInputField):
    """Input model for storage default mode (remote control command).

    Default mode values:
        0: Solar Power Only (Off)
        1: Charge from Clipped Solar Power
        2: Charge from Solar Power
        3: Charge from Solar Power and Grid
        4: Discharge to Maximize Export
        5: Discharge to Minimize Import
        7: Maximize Self Consumption
    """

    mode: int = Field(ge=0, le=7)

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: int) -> int:
        valid_modes = {0, 1, 2, 3, 4, 5, 7}
        if v not in valid_modes:
            raise ValueError(f"Invalid mode {v}. Valid modes are: {valid_modes}")
        return v


class StorageChargeLimitInput(BaseInputField):
    """Input model for storage charge limit in watts."""

    limit: float = Field(ge=0, le=1000000)


class StorageDischargeLimitInput(BaseInputField):
    """Input model for storage discharge limit in watts."""

    limit: float = Field(ge=0, le=1000000)


class StorageBackupReserveInput(BaseInputField):
    """Input model for storage backup reserve percentage."""

    percent: float = Field(ge=0, le=100)


class StorageCommandTimeoutInput(BaseInputField):
    """Input model for storage command timeout in seconds."""

    seconds: int = Field(ge=0, le=86400)


class ModbusStorageControlInput(BaseInputFieldEnumModel):
    """Enum of storage control input types."""

    CONTROL_MODE = "control_mode", StorageControlModeInput
    DEFAULT_MODE = "default_mode", StorageDefaultModeInput
    CHARGE_LIMIT = "charge_limit", StorageChargeLimitInput
    DISCHARGE_LIMIT = "discharge_limit", StorageDischargeLimitInput
    BACKUP_RESERVE = "backup_reserve", StorageBackupReserveInput
    COMMAND_TIMEOUT = "command_timeout", StorageCommandTimeoutInput
