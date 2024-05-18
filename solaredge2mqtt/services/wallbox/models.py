from pydantic import Field, field_serializer

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantEntityType as EntityType,
)
from solaredge2mqtt.services.models import Component


class WallboxInfo(Solaredge2MQTTBaseModel):
    manufacturer: str
    model: str
    version: str
    serialnumber: str

    def __init__(self, data: dict[str, str | int]) -> dict[str, str]:
        values = {
            "manufacturer": "SolarEdge",
            "model": data["model"],
            "version": data["firmwareVersion"],
            "serialnumber": data["serialNumber"],
        }

        super().__init__(**values)

    def homeassistant_device_info(self) -> dict[str, any]:
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

    info: WallboxInfo
    power: float = Field(**EntityType.POWER_W.field("Power"))
    state: str = Field(title="State")
    vehicle_plugged: bool = Field(**EntityType.PLUG.field("Vehicle plugged"))
    max_current: float = Field(**EntityType.CURRENT_A.field("Max current"))

    def __init__(self, data: dict[str, str | int]):
        info = WallboxInfo(data)
        power = round(data["meter"]["totalActivePower"] / 1000)
        state = data["state"]
        vehicle_connected = bool(data["vehiclePlugged"])
        max_current = float(data["maxCurrent"])

        super().__init__(
            info=info,
            power=power,
            state=state,
            vehicle_plugged=vehicle_connected,
            max_current=max_current,
        )

    def homeassistant_device_info(self) -> dict[str, any]:
        return self.info.homeassistant_device_info()

    @classmethod
    # pylint: disable=arguments-differ
    def model_json_schema(cls, mode: str = "serialization") -> dict[str, any]:
        schema = super().model_json_schema(mode=mode)
        schema["properties"].pop("info", None)
        return schema

    @field_serializer("vehicle_plugged")
    def serialize_vehicle_plugged(self, value: bool) -> str:
        return "true" if value else "false"
