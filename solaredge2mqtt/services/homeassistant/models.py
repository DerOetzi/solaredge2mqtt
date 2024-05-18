import base64
import hashlib

from pydantic import BaseModel, Field, computed_field

from solaredge2mqtt.core.models import EnumModel


class HomeAssistantBaseModel(BaseModel):
    client_id: str = Field(..., exclude=True)

    def hash_unique_id(self, ids: list[str | int]) -> str:
        ids.append(self.client_id)
        unique_id = "_".join([str(id) for id in ids])

        hash_obj = hashlib.sha256(unique_id.encode())
        hash_digest = hash_obj.digest()

        base64_encoded = base64.urlsafe_b64encode(hash_digest).decode()

        return base64_encoded[:10]


class HomeAssistantDevice(HomeAssistantBaseModel):
    name: str
    state_topic: str = Field(exclude=True)
    manufacturer: str | None = Field(None)
    model: str | None = Field(None)
    hw_version: str | None = Field(None)
    serial_number: str | None = Field(None)
    sw_version: str | None = Field(None)
    via_device: str | None = Field(None)

    @computed_field
    @property
    def identifiers(self) -> str:
        return self.hash_unique_id(
            [self.name, self.manufacturer, self.model, self.serial_number]
        )


class HomeAssistantEntityType(EnumModel):
    APPARENT_POWER = "apparent_power", "sensor", "apparent_power", "measurement", "VA"
    BATTERY = "battery", "sensor", "battery", "measurement", "%"
    CURRENT_A = "current_a", "sensor", "current", "measurement", "A"
    ENERGY_KWH = "energy_kwh", "sensor", "energy", "total_increasing", "kWh"
    ENERGY_WH = "energy_wh", "sensor", "energy", "total_increasing", "Wh"
    FREQUENCY_HZ = "frequency_hz", "sensor", "frequency", "measurement", "Hz"
    MONETARY = "monetary", "sensor", "monetary", None, None
    PERCENTAGE = "percentage", "sensor", None, "measurement", "%"
    PLUG = "plug", "binary_sensor", "plug", None, None
    POWER_FACTOR = "power_factor", "sensor", "power_factor", "measurement", "%"
    POWER_KW = "power_kw", "sensor", "power", "measurement", "kW"
    POWER_W = "power_w", "sensor", "power", "measurement", "W"
    REACTIVE_POWER = "reactive_power", "sensor", "reactive_power", "measurement", "VAr"
    VOLTAGE_V = "voltage_v", "sensor", "voltage", "measurement", "V"

    def __init__(
        self,
        key: str,
        typed: str,
        device_class: str | None = None,
        state_class: str | None = None,
        unit_of_measurement: str | None = None,
    ):
        self._key: str = key
        self._typed: str = typed
        self._device_class: str = device_class
        self._state_class: str | None = state_class
        self._unit_of_measurement: str | None = unit_of_measurement

    @property
    def typed(self) -> str:
        return self._typed

    @property
    def device_class(self) -> str:
        return self._device_class

    @property
    def state_class(self) -> str | None:
        return self._state_class

    @property
    def unit_of_measurement(self) -> str | None:
        return self._unit_of_measurement

    def field(
        self, title: str | None = None, icon: str | None = None
    ) -> dict[str, any]:
        json_schema_extra = {
            "ha_type": self,
            "icon": icon,
        }

        return {"title": title, "json_schema_extra": json_schema_extra}


class HomeAssistantEntity(HomeAssistantBaseModel):
    name: str
    device: HomeAssistantDevice
    _icon: str | None = None
    jsonpath: str | None = Field(None, exclude=True)
    ha_type: HomeAssistantEntityType = Field(exclude=True)
    unit: str | None = Field(None, exclude=True)

    def __init__(self, device: HomeAssistantDevice, icon: str | None = None, **data):
        super().__init__(client_id=device.client_id, device=device, **data)

        self._icon = icon

    @computed_field
    @property
    def unique_id(self) -> str:
        return self.hash_unique_id(
            [self.device.identifiers, self.name, self.state_topic, self.value_template]
        )

    @computed_field
    @property
    def state_topic(self) -> str:
        return self.device.state_topic

    @computed_field
    @property
    def value_template(self) -> str | None:
        return f"{{{{ value_json.{self.jsonpath} }}}}" if self.jsonpath else None

    @computed_field
    @property
    def state_class(self) -> str | None:
        return self.ha_type.state_class

    @computed_field
    @property
    def device_class(self) -> str | None:
        return self.ha_type.device_class

    @computed_field
    @property
    def unit_of_measurement(self) -> str | None:
        return self.ha_type.unit_of_measurement if self.unit is None else self.unit

    @computed_field
    @property
    def payload_on(self) -> str | None:
        return "true" if self.ha_type.typed == "binary_sensor" else None

    @computed_field
    @property
    def payload_off(self) -> str | None:
        return "false" if self.ha_type.typed == "binary_sensor" else None

    @computed_field
    @property
    def icon(self) -> str | None:
        return f"mdi:{self._icon}" if self._icon else None
