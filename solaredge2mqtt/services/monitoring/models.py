from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.models import HTTPResponse


class LogicalInfo(BaseModel):
    identifier: str
    serialnumber: str | None = Field(default=None)
    name: str
    type: str

    @staticmethod
    def map(data: HTTPResponse) -> dict[str, str]:
        if not isinstance(data, dict):
            raise InvalidDataException("Logical info data is not valid")

        return {
            "identifier": str(data["id"]),
            "serialnumber": data["serialNumber"],
            "name": data["name"],
            "type": data["type"],
        }


class LogicalInverter(BaseModel):
    info: LogicalInfo
    energy: float | None = Field(default=None)
    strings: list[LogicalString] = Field(default_factory=list)


class LogicalString(BaseModel):
    info: LogicalInfo
    energy: float | None = Field(default=None)
    modules: list[LogicalModule] = Field(default_factory=list)


class LogicalModule(BaseModel):
    info: LogicalInfo
    energy: float | None = Field(default=None)
    power: dict[datetime, float] | None = Field(default=None)

    @computed_field
    @property
    def power_today(self) -> dict[str, float] | None:
        power_today = None

        if self.power:
            power_today = {k.strftime("%H:%M"): v for k, v in self.power.items()}

        return power_today
