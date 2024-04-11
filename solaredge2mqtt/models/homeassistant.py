import base64
import hashlib

from pydantic import BaseModel, Field, computed_field


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
        return self.hash_unique_id([self.manufacturer, self.model, self.serial_number])


class HomeAssistantEntity(HomeAssistantBaseModel):
    name: str
    device: HomeAssistantDevice
    state_class: str | None = None
    unit_of_measurement: str | None = None
    jsonpath: str | None = Field(None, exclude=True)

    def __init__(self, device: HomeAssistantDevice, **data):
        super().__init__(client_id=device.client_id, device=device, **data)

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
