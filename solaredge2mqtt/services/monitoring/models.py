from __future__ import annotations

from pydantic import BaseModel


class LogicalInfo(BaseModel):
    id: str
    serialnumber: str | None
    name: str
    type: str

    @staticmethod
    def map(data: dict[str, str | int]) -> dict[str, str]:
        return {
            "id": str(data["id"]),
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
    energy: float | None
