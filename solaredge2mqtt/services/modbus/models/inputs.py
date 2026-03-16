from pydantic import Field

from solaredge2mqtt.core.models import (
    BaseInputFieldEnumModel,
    BaseInputScalarField,
)


class ModbusActivePowerLimitInput(BaseInputScalarField):
    limit: int = Field(ge=0, le=100)


class ModbusPowerControlInput(BaseInputFieldEnumModel):
    ACTIVE_POWER_LIMIT = "active_power_limit", ModbusActivePowerLimitInput
