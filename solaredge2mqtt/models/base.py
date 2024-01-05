from __future__ import annotations
from typing import Any, Dict, Optional, ClassVar

from enum import Enum

from pydantic import BaseModel, model_serializer


class EnumModel(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __str__(self) -> str:
        return str(self._value_)

    def __repr__(self) -> str:
        return str(self._value_)

    def __eq__(self, obj) -> bool:
        return isinstance(obj, self.__class__) and self.value == obj.value

    def __hash__(self):
        return hash(self.value)

    @classmethod
    def from_string(cls, value: str):
        for item in cls.__members__.values():
            if item.value == value:
                return item
        raise ValueError(f"No enum value {value} found.")

    @model_serializer
    def serialize(self):
        return self.value


class InfluxDBModel(BaseModel):
    def influxdb_fields(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        fields = {}
        for attr, value in self.__dict__.items():
            if attr == "info":
                continue
            if isinstance(value, InfluxDBModel):
                attr_name = attr
                if prefix is not None:
                    attr_name = f"{prefix}_{attr_name}"
                fields = {**fields, **value.influxdb_fields(attr_name)}
            else:
                if prefix is not None:
                    attr = f"{prefix}_{attr}"
                fields[attr] = float(value) if isinstance(value, int) else value
        return fields


class ComponentValueGroup(InfluxDBModel):
    @staticmethod
    def scale_value(
        data: Dict[str, str | int],
        value_key: str,
        scale_key: Optional[str] = None,
        digits: Optional[int] = 2,
    ) -> float:
        if scale_key is None:
            scale_key = f"{value_key}_scale"

        value = int(data[value_key])
        scale = int(data[scale_key])

        return round(value * 10**scale, digits)

    # @staticmethod
    # def is_three_phase(data: Dict[str, Any]) -> bool:
    #     return data["c_sunspec_did"] in [
    #         sunspecDID.THREE_PHASE_INVERTER.value,
    #         sunspecDID.WYE_THREE_PHASE_METER.value,
    #         sunspecDID.DELTA_THREE_PHASE_METER.value,
    #     ]


class Component(ComponentValueGroup):
    COMPONENT: ClassVar[str] = "unknown"
    SOURCE: ClassVar[str] = "unknown"

    @property
    def influxdb_tags(self) -> Dict[str, str]:
        return {
            "component": self.COMPONENT,
            "source": self.SOURCE,
        }
