from __future__ import annotations

from abc import abstractmethod
from typing import Any, Self, cast

from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.core.models import EnumModel, Solaredge2MQTTBaseModel
from solaredge2mqtt.services.modbus.models.values import MixinModbusSunSpecScaleValue
from solaredge2mqtt.services.modbus.sunspec.values import (
    C_SUNSPEC_DID_MAP,
    SunSpecPayload,
)
from solaredge2mqtt.services.models import Component


class ModbusUnitRole(EnumModel):
    LEADER = "leader"
    FOLLOWER = "follower"
    CUMULATED = "cumulated"

    def __init__(self, role: str):
        self._role: str = role

    @property
    def role(self) -> str:
        return self._role


class ModbusUnitInfo(Solaredge2MQTTBaseModel):
    unit: int
    key: str
    role: ModbusUnitRole


class ModbusDeviceInfo(Solaredge2MQTTBaseModel):
    manufacturer: str
    model: str
    option: str | None = None
    sunspec_type: str
    version: str
    serialnumber: str
    unit: ModbusUnitInfo | None = None

    @classmethod
    def from_sunspec(
        cls,
        payload: SunSpecPayload,
        unit: ModbusUnitInfo | None = None
    ) -> ModbusDeviceInfo:
        return cls(**{"unit": unit, **cls._extract_from_sunspec_payload(payload)})

    @staticmethod
    def _extract_from_sunspec_payload(data: SunSpecPayload) -> dict[str, Any]:
        values: dict[str, Any] = {
            "manufacturer": data["c_manufacturer"],
            "model": data["c_model"],
            "version": data["c_version"],
            "serialnumber": data["c_serialnumber"]
        }

        if "c_sunspec_did" in data and data["c_sunspec_did"] in C_SUNSPEC_DID_MAP:
            values["sunspec_type"] = C_SUNSPEC_DID_MAP[int(
                data["c_sunspec_did"])]
        else:
            values["sunspec_type"] = "Unknown"

        if "c_option" in data:
            values["option"] = data["c_option"]

        return values

    def homeassistant_device_info(self, name: str) -> dict[str, Any]:
        info = {
            "name": f"SolarEdge {name}",
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hw_version": self.version,
            "serial_number": self.serialnumber
        }

        if self.unit:
            info["unit_key"] = self.unit.key

        return info

    def unit_key(self, suffix: str = "") -> str:
        return f"{self.unit.key}{suffix}" if self.unit else ""


class ModbusComponent(Component, MixinModbusSunSpecScaleValue):
    SOURCE = "modbus"

    info: SkipJsonSchema[ModbusDeviceInfo]

    def model_dump_influxdb(self, exclude: set[str] | None = None) -> dict[str, Any]:
        return super().model_dump_influxdb({"info", *exclude} if exclude else {"info"})

    @classmethod
    def from_sunspec(
        cls, info: ModbusDeviceInfo, payload: SunSpecPayload
    ) -> Self:
        values = cls.extract_sunspec_payload(payload)
        return cast(Self, cls(info=info, **values))

    @classmethod
    @abstractmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        pass

    @property
    def influxdb_tags(self) -> dict[str, str]:
        tags = {
            **super().influxdb_tags,
            "manufacturer": self.info.manufacturer,
            "model": self.info.model,
            "sunspec_type": self.info.sunspec_type,
            "serialnumber": self.info.serialnumber,
        }

        if self.info.option:
            tags["option"] = self.info.option

        return tags

    def mqtt_topic(self, has_followers: bool = False) -> str:
        unit_key = (
            self.info.unit.key
            if has_followers and self.info.unit
            else None
        )
        return self.generate_topic_prefix(unit_key)

    def homeassistant_device_info(self) -> dict[str, str]:
        raise NotImplementedError("Not used in ModbusComponent")

    @classmethod
    def generate_topic_prefix(cls, unit_key: str | None = None) -> str:
        topic_parts = ["modbus"]

        if unit_key:
            topic_parts.append(unit_key)

        topic_parts.append(cls.COMPONENT)

        return "/".join(topic_parts)
