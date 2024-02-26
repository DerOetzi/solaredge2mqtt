from __future__ import annotations

from collections.abc import MutableMapping
from enum import Enum
from typing import ClassVar

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

    def __eq__(self, other) -> bool:
        return isinstance(other, self.__class__) and self.value == other.value

    def __hash__(self):
        return hash(self.value)

    @classmethod
    def from_string(cls, value: str) -> EnumModel:
        for item in cls.__members__.values():
            if item.value == value:
                return item
        raise ValueError(f"No enum value {value} found.")

    @model_serializer
    def serialize(self) -> any:
        return self.value


class Solaredge2MQTTBaseModel(BaseModel):
    def model_dump_influxdb(self, exclude: list[str] | None = None) -> dict[str, any]:
        return self._flatten_dict(self.model_dump(exclude=exclude, exclude_none=True))

    def _flatten_dict(self, d: MutableMapping, parent_key: str = "") -> MutableMapping:
        items = []
        for k, v in d.items():
            new_key = parent_key + "_" + k if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(self._flatten_dict(v, new_key).items())
            else:
                items.append((new_key, float(v) if isinstance(v, int) else v))
        return dict(items)


class ComponentValueGroup(Solaredge2MQTTBaseModel):
    @staticmethod
    def scale_value(
        data: dict[str, str | int],
        value_key: str,
        scale_key: str | None = None,
        digits: int = 2,
    ) -> float:
        if scale_key is None:
            scale_key = f"{value_key}_scale"

        value = int(data[value_key])
        scale = int(data[scale_key])

        return round(value * 10**scale, digits)


class Component(ComponentValueGroup):
    COMPONENT: ClassVar[str] = "unknown"
    SOURCE: ClassVar[str] = "unknown"

    @property
    def influxdb_tags(self) -> dict[str, str]:
        return {
            "component": self.COMPONENT,
            "source": self.SOURCE,
        }

    @property
    def mqtt_topic(self) -> str:
        return f"{self.SOURCE}/{self.COMPONENT}"
