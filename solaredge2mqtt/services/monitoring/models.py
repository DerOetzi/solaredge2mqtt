from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, field_serializer
from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType as HABinarySensor,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantNumberType as HANumber,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import Component, HTTPResponsePayload
from solaredge2mqtt.services.monitoring.inputs import EVChargerControlInput


class LogicalInfo(BaseModel):
    identifier: str
    serialnumber: str | None = Field(default=None)
    name: str
    type: str

    @staticmethod
    def map(data: HTTPResponsePayload) -> dict[str, str]:
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


class EVChargerInfo(Solaredge2MQTTBaseModel):
    manufacturer: str
    model: str
    version: str
    serialnumber: str
    name: str
    reporter_id: int

    @classmethod
    def from_device(cls, device: dict[str, Any]) -> EVChargerInfo:
        try:
            return cls(
                manufacturer=str(device["manufacturer"]),
                model=str(device["model"]),
                version=str(device["swVersion"]),
                serialnumber=str(device["serialNumber"]),
                name=str(device["name"]),
                reporter_id=int(device["reporterId"]),
            )
        except KeyError as e:
            raise InvalidDataException(f"Missing key in EV charger data: {e}")

    def homeassistant_device_info(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "sw_version": self.version,
            "serial_number": self.serialnumber,
        }


class EVCharger(Component):
    COMPONENT = "evcharger"
    SOURCE = "monitoring"
    AVAILABILITY_SERVICE = "monitoring"

    info: SkipJsonSchema[EVChargerInfo]

    charge_level: int = Field(
        **HANumber.EV_CHARGE_LEVEL.field(
            "Charge level", input_field=EVChargerControlInput.CHARGE_LEVEL
        )
    )
    charger_status: str = Field(**HASensor.STATUS.field("Charger status"))
    connected: bool = Field(**HABinarySensor.PLUG.field("Vehicle connected"))
    session_energy: int = Field(
        **HASensor.ENERGY_MEASUREMENT_WH.field("Session energy")
    )
    rated_power: float = Field(**HASensor.POWER_W.field("Rated power"))

    @classmethod
    def from_device(cls, device: dict[str, Any]) -> EVCharger:
        info = EVChargerInfo.from_device(device)

        try:
            connected = device.get("connectionStatus") == "CONNECTED" or bool(
                device.get("sessionActive")
            )

            action_op = next(
                (d.get("actionOp") for d in device.get("actionOperationDetails", [])),
                None,
            )
            charge_level = 100 if action_op == "OFF" else 0

            return cls(
                info=info,
                charge_level=charge_level,
                charger_status=str(device["chargerStatus"]),
                connected=connected,
                session_energy=int(device["sessionEnergy"]),
                rated_power=float(device["ratedPower"]),
            )
        except KeyError as e:
            raise InvalidDataException(f"Missing key in EV charger data: {e}")

    def mqtt_topic(self) -> str:
        return f"monitoring/evcharger/{self.info.reporter_id}"

    def mqtt_chargelevel_topic(self) -> str:
        return f"{self.mqtt_topic()}/charge_level"

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self.info.homeassistant_device_info()

    @field_serializer("connected")
    def serialize_connected(self, value: bool) -> str:
        return "true" if value else "false"
