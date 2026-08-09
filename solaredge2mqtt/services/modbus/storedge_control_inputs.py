from typing import Any

from pydantic import Field

from solaredge2mqtt.core.models import BaseInputScalarField


class ForceableScalarInput(BaseInputScalarField):
    """A scalar input with an optional force flag.

    A bare scalar payload (e.g. publishing plain `4`) still maps to the
    single value field, defaulting force to False. Publishing a JSON object
    can additionally set `"force": true` to bypass no-op write skipping,
    e.g. because the cached last-known value may be stale.
    """

    force: bool = Field(default=False)

    @classmethod
    def _wrap_scalar(cls, scalar: Any) -> dict[str, Any]:
        value_field = next(name for name in cls.model_fields if name != "force")
        return {value_field: scalar}


class StoredgeControlModeInput(ForceableScalarInput):
    mode: int = Field(ge=0, le=4)


class StoredgeAcChargePolicyInput(ForceableScalarInput):
    policy: int = Field(ge=0, le=3)


class StoredgeAcChargeLimitInput(ForceableScalarInput):
    limit: float = Field(ge=0)


class StoredgeBackupReservedSettingInput(ForceableScalarInput):
    percentage: float = Field(ge=0, le=100)


class StoredgeDefaultModeInput(ForceableScalarInput):
    mode: int = Field(ge=0, le=7)


class StoredgeCommandTimeoutInput(ForceableScalarInput):
    seconds: int = Field(ge=0, le=86400)


class StoredgeCommandModeInput(ForceableScalarInput):
    mode: int = Field(ge=0, le=7)


class StoredgeChargeLimitInput(ForceableScalarInput):
    limit: float = Field(ge=0)


class StoredgeDischargeLimitInput(ForceableScalarInput):
    limit: float = Field(ge=0)
