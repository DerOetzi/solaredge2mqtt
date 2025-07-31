from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field


class LogicalInfo(BaseModel):
    identifier: str
    serialnumber: str | None
    name: str
    type: str

    @staticmethod
    def map(data: dict[str, str | int]) -> dict[str, str]:
        return {
            "identifier": str(data["id"]),
            "serialnumber": data["serialNumber"],
            "name": data["name"],
            "type": data["type"],
        }


class LogicalInverter(BaseModel):
    info: LogicalInfo
    energy: float | None
    strings: list[LogicalString] = []


class LogicalString(BaseModel):
    info: LogicalInfo
    energy: float | None
    modules: list[LogicalModule] = []


class LogicalModule(BaseModel):
    info: LogicalInfo
    energy: float | None = Field(None)
    power: dict[datetime, float] | None = Field(None)

    @computed_field
    @property
    def power_today(self) -> dict[str, float] | None:
        power_today = None

        if self.power:
            power_today = {
                k.strftime("%H:%M"): v
                for k, v in self.power.items()
            }

        return power_today
