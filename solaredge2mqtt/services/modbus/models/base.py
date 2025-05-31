from __future__ import annotations

from solaredge2mqtt.core.models import EnumModel, Solaredge2MQTTBaseModel
from solaredge2mqtt.services.modbus.sunspec.values import C_SUNSPEC_DID_MAP
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

    def __init__(self, data: dict[str, str | int]):
        values = {
            "manufacturer": data["c_manufacturer"],
            "model": data["c_model"],
            "version": data["c_version"],
            "serialnumber": data["c_serialnumber"]
        }

        if "unit" in data:
            values["unit"] = data["unit"]

        if "c_sunspec_did" in data and data["c_sunspec_did"] in C_SUNSPEC_DID_MAP:
            values["sunspec_type"] = C_SUNSPEC_DID_MAP[data["c_sunspec_did"]]
        else:
            values["sunspec_type"] = "Unknown"

        if "c_option" in data:
            values["option"] = data["c_option"]

        super().__init__(**values)

    def homeassistant_device_info(self, name: str) -> dict[str, any]:
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

    @property
    def has_unit(self) -> bool:
        return self.unit is not None

    def unit_key(self, suffix: str = "") -> str:
        return f"{self.unit.key}{suffix}" if self.has_unit else ""


class ModbusComponent(Component):
    SOURCE = "modbus"

    info: ModbusDeviceInfo

    def model_dump_influxdb(self, exclude: list[str] | None = None) -> dict[str, any]:
        return super().model_dump_influxdb(["info", *exclude] if exclude else ["info"])

    @property
    def influxdb_tags(self) -> dict[str, str]:
        return {
            **super().influxdb_tags,
            "manufacturer": self.info.manufacturer,
            "model": self.info.model,
            "option": self.info.option,
            "sunspec_type": self.info.sunspec_type,
            "serialnumber": self.info.serialnumber,
        }

    @classmethod
    # pylint: disable=arguments-differ
    def model_json_schema(cls, mode: str = "serialization") -> dict[str, any]:
        schema = super().model_json_schema(mode=mode)
        schema["properties"].pop("info", None)
        return schema

    def homeassistant_device_info(self) -> dict[str, any]:
        return self.info.homeassistant_device_info()

    def mqtt_topic(self, has_followers: bool = False) -> str:
        return self.generate_topic_prefix(self.info.unit.key if has_followers else None)

    @classmethod
    def generate_topic_prefix(cls, unit_key: str | None = None) -> str:
        topic_parts = [cls.SOURCE]

        if unit_key:
            topic_parts.append(unit_key)

        topic_parts.append(cls.COMPONENT)

        return "/".join(topic_parts)

    @property
    def has_unit(self) -> bool:
        return self.info.has_unit
