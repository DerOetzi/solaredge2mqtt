from __future__ import annotations

from typing import Any

from pydantic import Field, field_serializer
from pydantic.json_schema import SkipJsonSchema

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBinarySensorType as HABinarySensor,
)
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import Component, HTTPResponse


class WallboxInfo(Solaredge2MQTTBaseModel):
    manufacturer: str
    model: str
    version: str
    serialnumber: str

    @classmethod
    def from_http_response(cls, response: dict[str, Any]) -> WallboxInfo:
        try:
            values = {
                "manufacturer": "SolarEdge",
                "model": response["model"],
                "version": response["firmwareVersion"],
                "serialnumber": response["serialNumber"],
            }

            return cls(**values)
        except KeyError as e:
            raise InvalidDataException(f"Missing key in Wallbox data: {e}")

    def homeassistant_device_info(self) -> dict[str, Any]:
        return {
            "name": f"{self.manufacturer} Wallbox",
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hw_version": self.version,
            "serial_number": self.serialnumber,
        }


class WallboxAPI(Component):
    COMPONENT = "wallbox"
    SOURCE = "api"

    info: SkipJsonSchema[WallboxInfo]

    power: int = Field(**HASensor.POWER_W.field("Power"))
    state: str = Field(title="State")
    vehicle_plugged: bool = Field(**HABinarySensor.PLUG.field("Vehicle plugged"))
    max_current: float = Field(**HASensor.CURRENT_A.field("Max current"))

    @classmethod
    def from_http_response(cls, response: HTTPResponse) -> WallboxAPI:
        if not isinstance(response, dict):
            raise InvalidDataException("Invalid Wallbox data")

        info = WallboxInfo.from_http_response(response)

        try:
            power = round(float(response["meter"]["totalActivePower"]) / 1000)
            state = str(response["state"])
            vehicle_connected = bool(response["vehiclePlugged"])
            max_current = float(response["maxCurrent"])

            return cls(
                info=info,
                power=power,
                state=state,
                vehicle_plugged=vehicle_connected,
                max_current=max_current,
            )
        except KeyError as e:
            raise InvalidDataException(f"Missing key in Wallbox data: {e}")

    def homeassistant_device_info(self) -> dict[str, Any]:
        return self.info.homeassistant_device_info()

    @field_serializer("vehicle_plugged")
    def serialize_vehicle_plugged(self, value: bool) -> str:
        return "true" if value else "false"
