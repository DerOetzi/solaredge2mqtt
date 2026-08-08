from pydantic import Field

from solaredge2mqtt.core.models import BaseInputScalarField


class StorageControlModeInput(BaseInputScalarField):
    mode: int = Field(ge=0, le=4)


class StorageAcChargePolicyInput(BaseInputScalarField):
    policy: int = Field(ge=0, le=3)


class StorageAcChargeLimitInput(BaseInputScalarField):
    limit: float = Field(ge=0)


class StorageBackupReservedSettingInput(BaseInputScalarField):
    percentage: float = Field(ge=0, le=100)


class StorageDefaultModeInput(BaseInputScalarField):
    mode: int = Field(ge=0, le=7)


class RemoteControlCommandTimeoutInput(BaseInputScalarField):
    seconds: int = Field(ge=0, le=86400)


class RemoteControlCommandModeInput(BaseInputScalarField):
    mode: int = Field(ge=0, le=7)


class RemoteControlChargeLimitInput(BaseInputScalarField):
    limit: float = Field(ge=0)


class RemoteControlDischargeLimitInput(BaseInputScalarField):
    limit: float = Field(ge=0)
