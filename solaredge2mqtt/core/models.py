from __future__ import annotations

from collections.abc import MutableMapping
from datetime import datetime, timezone
from enum import Enum

import jsonref
from pydantic import BaseModel, model_serializer, model_validator

from solaredge2mqtt import __version__


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


class BaseInputField(BaseModel):
    model_config = {
        "extra": "forbid"
    }


class BaseInputFieldEnumModel(EnumModel):
    def __init__(self, key: str, input_model: type[BaseInputField]):
        self._key: str = key
        self._input_model: type[BaseInputField] = input_model

    @property
    def key(self) -> str:
        return self._key

    @property
    def input_model(self) -> type[BaseInputField]:
        return self._input_model


class BaseField(EnumModel):
    def __init__(self, key: str, input_field: BaseInputFieldEnumModel | None = None):
        self._key: str = key
        self._input_field: BaseInputFieldEnumModel | None = input_field

    def field(self, title: str | None,
              json_schema_extra: dict[str, any] | None = None,
              input_field: BaseInputFieldEnumModel | None = None) -> dict[str, any]:

        if json_schema_extra is None:
            json_schema_extra = {}

        input_field = input_field or self._input_field

        if input_field:
            json_schema_extra = {
                "input_field": input_field.key,
                **json_schema_extra,
            }
        else:
            json_schema_extra = {
                "input_field": None,
                **json_schema_extra,
            }

        return {"title": title, "json_schema_extra": json_schema_extra}


class Solaredge2MQTTBaseModel(BaseModel):
    timestamp: datetime | None = None

    @model_validator(mode="before")
    def _set_always(cls, data: dict[str, any]) -> dict[str, any]:
        data = dict(data or {})
        if "timestamp" not in data or data["timestamp"] is None:
            data["timestamp"] = datetime.now(tz=timezone.utc)
        return data

    def model_dump_influxdb(self, exclude: list[str] | None = None) -> dict[str, any]:
        ignore_keys = {"timestamp"}
        return self._flatten_dict(
            self.model_dump(exclude=exclude, exclude_none=True),
            ignore_keys=ignore_keys
        )

    def _flatten_dict(
        self,
        d: MutableMapping,
        ignore_keys: set[str] = set(),
        join_chr: str = "_",
        parent_key: str = "",
    ) -> MutableMapping:
        items = []
        for k, v in d.items():
            if k in ignore_keys:
                continue
            new_key = parent_key + join_chr + k if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(
                    self._flatten_dict(
                        v, ignore_keys, join_chr, new_key
                    ).items()
                )
            else:
                if isinstance(v, int):
                    v = float(v)
                elif isinstance(v, datetime):
                    v = v.isoformat()

                items.append((new_key, v))
        return dict(items)

    def _default_homeassistant_device_info(self, name: str) -> dict[str, any]:
        return {
            "name": f"SolarEdge2MQTT {name}",
            "manufacturer": "DerOetzi",
            "model": "SolarEdge2MQTT",
            "sw_version": __version__,
        }

    @classmethod
    def parse_schema(cls, property_parser: callable | None = None) -> list[dict]:
        return cls._walk_schema(
            jsonref.replace_refs(
                cls.model_json_schema(mode="serialization"),
                merge_props=True
            )[
                "properties"
            ], property_parser or cls.property_parser

        )

    @classmethod
    def _walk_schema(
        cls,
        properties: dict[str, dict],
        property_parser: callable,
        parent_name: str | None = None,
        parent_path: list[str] = []
    ) -> list[dict]:
        items: list[dict] = []
        for key, prop in properties.items():
            new_path = [*parent_path, key]
            new_name = (
                parent_name + " " +
                prop["title"] if parent_name else prop["title"]
            )
            if "properties" in prop:
                items.extend(
                    cls._walk_schema(
                        prop["properties"], property_parser, new_name, new_path
                    )
                )
            elif "allOf" in prop:
                items.extend(
                    cls._walk_schema(
                        prop["allOf"][0]["properties"],
                        property_parser,
                        new_name,
                        new_path
                    )
                )
            elif "anyOf" in prop and "properties" in prop["anyOf"][0]:
                items.extend(
                    cls._walk_schema(
                        prop["anyOf"][0]["properties"],
                        property_parser,
                        new_name,
                        new_path
                    )
                )
            else:
                item = property_parser(prop, new_name, new_path)
                if item:
                    items.append(item)

        return items

    @staticmethod
    def property_parser(
        prop: dict[str, any],
        name: str,
        path: list[str],
    ) -> dict | None:
        if "input_field" in prop:
            return {
                "name": name,
                "path": path,
                "input_field": prop["input_field"],
            }
