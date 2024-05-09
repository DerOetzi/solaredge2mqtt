from __future__ import annotations

import logging
from collections.abc import MutableMapping
from datetime import datetime
from enum import Enum
from typing import ClassVar

import jsonref
from pydantic import BaseModel, model_serializer

from solaredge2mqtt import __version__
from solaredge2mqtt.core.events.events import BaseEvent


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

    def _flatten_dict(
        self, d: MutableMapping, join_chr: str = "_", parent_key: str = ""
    ) -> MutableMapping:
        items = []
        for k, v in d.items():
            new_key = parent_key + join_chr + k if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(self._flatten_dict(v, join_chr, new_key).items())
            else:
                if isinstance(v, int):
                    v = float(v)
                elif isinstance(v, datetime):
                    v = v.isoformat()

                items.append((new_key, v))
        return dict(items)

    @classmethod
    def _walk_schema_for_homeassistant_entities(
        cls,
        properties: dict[str, dict],
        parent_jsonpath: str | None = None,
        parent_name: str | None = None,
    ) -> list[dict]:
        items: list[dict] = []
        for key, prop in properties.items():
            new_jsonpath = parent_jsonpath + "." + key if parent_jsonpath else key
            new_name = (
                parent_name + " " + prop["title"] if parent_name else prop["title"]
            )
            if "properties" in prop:
                items.extend(
                    cls._walk_schema_for_homeassistant_entities(
                        prop["properties"], new_jsonpath, new_name
                    )
                )
            elif "allOf" in prop:
                items.extend(
                    cls._walk_schema_for_homeassistant_entities(
                        prop["allOf"][0]["properties"], new_jsonpath, new_name
                    )
                )
            elif "anyOf" in prop and "properties" in prop["anyOf"][0]:
                items.extend(
                    cls._walk_schema_for_homeassistant_entities(
                        prop["anyOf"][0]["properties"], new_jsonpath, new_name
                    )
                )
            else:
                entity: dict = {"name": new_name, "jsonpath": new_jsonpath}

                if "ha_type" in prop:
                    entity["ha_type"] = prop["ha_type"]
                    entity["icon"] = prop["icon"]
                    items.append(entity)

        return items

    def _default_homeassistant_device_info(self, name: str) -> dict[str, any]:
        return {
            "name": f"SolarEdge2MQTT {name}",
            "manufacturer": "DerOetzi",
            "model": "SolarEdge2MQTT",
            "sw_version": __version__,
        }

    @classmethod
    def homeassistant_entities_info(cls) -> list[dict]:
        return cls._walk_schema_for_homeassistant_entities(
            jsonref.replace_refs(cls.model_json_schema(mode="serialization"))[
                "properties"
            ]
        )


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
    SOURCE: ClassVar[str | None] = None

    @property
    def influxdb_tags(self) -> dict[str, str]:
        return {
            "component": self.COMPONENT,
            "source": self.SOURCE,
        }

    def mqtt_topic(self) -> str:
        if self.SOURCE:
            topic = f"{self.SOURCE}/{self.COMPONENT}"
        else:
            topic = self.COMPONENT

        return topic

    def __str__(self) -> str:
        if self.SOURCE:
            name = f"{self.SOURCE}: {self.COMPONENT}"
        else:
            name = self.COMPONENT

        return name


class ComponentEvent(BaseEvent):
    def __init__(self, component: Component):
        self._component = component

    @property
    def component(self) -> Component:
        return self._component

    def __str__(self) -> str:
        return str(self._component)


class ComponentsEvent(BaseEvent):
    def __init__(self, components: dict[str, Component]):
        self._components = components

    @property
    def components(self) -> dict[str, Component]:
        return self._components

    def __str__(self) -> str:
        return str(self._components)


class IntervalBaseTriggerEvent(BaseEvent):
    pass


class Interval10MinTriggerEvent(IntervalBaseTriggerEvent):
    pass
