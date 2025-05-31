from pydantic import Field

from solaredge2mqtt.core.models import BaseInputField, BaseInputFieldEnumModel


class ModbusActivePowerLimitInput(BaseInputField):
    limit: int = Field(min=0, max=100)


class ModbusPowerControlInput(BaseInputFieldEnumModel):
    ACTIVE_POWER_LIMIT = "active_power_limit", ModbusActivePowerLimitInput
