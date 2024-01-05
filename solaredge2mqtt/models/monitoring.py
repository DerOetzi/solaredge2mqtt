from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel


class LogicalInfo(BaseModel):
    id: str
    serialnumber: Optional[str]
    name: str
    type: str

    @staticmethod
    def map(data: Dict[str, str | int]) -> Dict[str, str]:
        return {
            "id": str(data["id"]),
            "serialnumber": data["serialNumber"],
            "name": data["name"],
            "type": data["type"],
        }


class LogicalInverter(BaseModel):
    info: LogicalInfo
    energy: Optional[float]
    strings: list[LogicalString] = []


class LogicalString(BaseModel):
    info: LogicalInfo
    energy: Optional[float]
    modules: list[LogicalModule] = []


class LogicalModule(BaseModel):
    info: LogicalInfo
    energy: Optional[float]
