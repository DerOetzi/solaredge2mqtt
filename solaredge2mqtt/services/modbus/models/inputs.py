from pydantic import Field

from solaredge2mqtt.core.models import BaseInputField, BaseInputFieldEnumModel


class ModbusActivePowerLimitInput(BaseInputField):
    limit: int = Field(ge=0, le=100)


class ModbusPowerControlInput(BaseInputFieldEnumModel):
    ACTIVE_POWER_LIMIT = "active_power_limit", ModbusActivePowerLimitInput


class ModbusStorageChargeLimitInput(BaseInputField):
    """Input model for setting the storage charge limit in watts."""

    limit: float = Field(ge=0, le=1000000)


class ModbusStorageDischargeLimitInput(BaseInputField):
    """Input model for setting the storage discharge limit in watts."""

    limit: float = Field(ge=0, le=1000000)


class ModbusStorageCommandModeInput(BaseInputField):
    """Input model for setting the storage command mode.

    Valid modes:
    - 0: Off
    - 1: Charge from Clipped Solar Power
    - 2: Charge from Solar Power
    - 3: Charge from Solar Power and Grid
    - 4: Discharge to Maximize Export
    - 5: Discharge to Minimize Import
    - 7: Maximize Self Consumption
    """

    mode: int = Field(ge=0, le=7)


class ModbusStorageCommandTimeoutInput(BaseInputField):
    """Input model for setting the storage command timeout in seconds."""

    timeout: int = Field(ge=0, le=86400)


class ModbusStorageControlInput(BaseInputFieldEnumModel):
    """Enum of storage control input fields for MQTT subscription."""

    CHARGE_LIMIT = "charge_limit", ModbusStorageChargeLimitInput
    DISCHARGE_LIMIT = "discharge_limit", ModbusStorageDischargeLimitInput
    COMMAND_MODE = "command_mode", ModbusStorageCommandModeInput
    COMMAND_TIMEOUT = "command_timeout", ModbusStorageCommandTimeoutInput
