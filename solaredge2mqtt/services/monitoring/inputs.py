from pydantic import Field

from solaredge2mqtt.core.models import (
    BaseInputFieldEnumModel,
    BaseInputScalarField,
)


class EVChargerChargeLevelInput(BaseInputScalarField):
    level: int = Field(ge=0, le=100)


class EVChargerControlInput(BaseInputFieldEnumModel):
    CHARGE_LEVEL = "charge_level", EVChargerChargeLevelInput
