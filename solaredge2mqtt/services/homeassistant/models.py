from __future__ import annotations

import base64
import hashlib
import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

from solaredge2mqtt.core.models import (
    BaseField,
    BaseInputField,
    BaseInputFieldEnumModel,
    EnumModel,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.models import BaseInputFieldEnumModel


class HomeAssistantStatus(EnumModel):
    ONLINE = "online"
    OFFLINE = "offline"

    def __init__(self, status: str):
        self._status: str = status

    @property
    def status(self) -> str:
        return self._status


class HomeAssistantStatusInput(BaseInputField):
    status: HomeAssistantStatus

    def __init__(self, status: str):
        super().__init__(status=status)


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
    unit_key: str | None = Field(None, exclude=True)

    @computed_field
    @property
    def identifiers(self) -> str:
        identifiers = [self.name, self.manufacturer,
                       self.model, self.serial_number]

        if self.unit_key:
            identifiers.append(self.unit_key)

        return self.hash_unique_id(
            identifiers
        )


class HomeAssistantType(EnumModel):
    BINARY_SENSOR = "binary_sensor", False, []
    NUMBER = "number", True, ["min", "max", "step", "mode"]
    SENSOR = "sensor", False, []

    def __init__(
        self,
        identifier: str,
        command_topic: bool,
        additional_fields: list[str]
    ):
        self._identifier: str = identifier
        self._command_topic: bool = command_topic
        self._additional_fields: list[str] = additional_fields

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def command_topic(self) -> bool:
        return self._command_topic

    @property
    def additional_fields(self) -> list[str]:
        return self._additional_fields


class HomeAssistantEntityBaseType(BaseField):
    def __init__(
        self,
        key: str,
        typed: HomeAssistantType,
        device_class: str | None = None,
        state_class: str | None = None,
        unit_of_measurement: str | None = None,
    ):
        super().__init__(key)

        self._typed: HomeAssistantType = typed
        self._device_class: str | None = device_class
        self._state_class: str | None = state_class
        self._unit_of_measurement: str | None = unit_of_measurement

    @property
    def typed(self) -> HomeAssistantType:
        return self._typed

    @property
    def device_class(self) -> str | None:
        return self._device_class

    @property
    def state_class(self) -> str | None:
        return self._state_class

    @property
    def unit_of_measurement(self) -> str | None:
        return self._unit_of_measurement

    def field(
        self,
        title: str | None = None,
        icon: str | None = None,
        json_schema_extra: dict[str, any] | None = None,
        input_field: BaseInputFieldEnumModel | None = None
    ) -> dict[str, any]:
        if json_schema_extra is None:
            json_schema_extra = {}

        json_schema_extra = {
            "ha_type": self,
            "ha_typed": self.typed.identifier,
            "icon": icon,
            **json_schema_extra
        }

        return super().field(title, json_schema_extra, input_field)


class HomeAssistantBinarySensorType(HomeAssistantEntityBaseType):
    ENABLED = "enabled", None, None
    GRID_STATUS = "grid_status", "power", None
    PLUG = "plug", "plug", None

    def __init__(
        self,
        key: str,
        device_class: str | None = None,
        state_class: str | None = None,
    ):
        super().__init__(
            key,
            HomeAssistantType.BINARY_SENSOR,
            device_class,
            state_class,
            None,
        )


class HomeAssistantNumberType(HomeAssistantEntityBaseType):
    ACTIVE_POWER_LIMIT = "active_power_limit", None, '%', 0, 100, 1, "slider"

    def __init__(
        self,
        key: str,
        device_class: str | None = None,
        unit_of_measurement: str | None = None,
        min: int | float | None = None,
        max: int | float | None = None,
        step: int | float | None = None,
        mode: str | None = None,
    ):
        super().__init__(key, HomeAssistantType.NUMBER,
                         device_class, None, unit_of_measurement)

        self._min: int | float | None = min
        self._max: int | float | None = max
        self._step: int | float | None = step
        self._mode: str | None = mode

    def field(
        self,
        input_field: BaseInputFieldEnumModel,
        title: str | None = None,
        icon: str | None = None,
        min: float | None = None,
        max: float | None = None,
        step: float | None = None,
        mode: str | None = None
    ) -> dict[str, any]:
        json_schema_extra = {
            "min": min or self._min,
            "max": max or self._max,
            "step": step or self._step,
            "mode": mode or self._mode,
        }

        return super().field(title, icon, json_schema_extra, input_field)


class HomeAssistantSensorType(HomeAssistantEntityBaseType):
    APPARENT_POWER = "apparent_power", "apparent_power", "measurement", "VA"
    BATTERY = "battery", "battery", "measurement", "%"
    CURRENT_A = "current_a", "current", "measurement", "A"
    ENERGY_KWH = "energy_kwh", "energy", "total_increasing", "kWh"
    ENERGY_WH = "energy_wh", "energy", "total_increasing", "Wh"
    FREQUENCY_HZ = "frequency_hz", "frequency", "measurement", "Hz"
    MONETARY = "monetary", "monetary", "total", None
    MONETARY_BALANCE = "monetary_balance", "monetary", None, None
    PERCENTAGE = "percentage", None, "measurement", "%"
    POWER_FACTOR = "power_factor", "power_factor", "measurement", "%"
    POWER_KW = "power_kw", "power", "measurement", "kW"
    POWER_W = "power_w", "power", "measurement", "W"
    REACTIVE_POWER = "reactive_power", "reactive_power", "measurement", "var"
    STATUS = "status", None, None, None
    TEMP_C = "temp_c", "temperature", "measurement", "°C"
    VOLTAGE_V = "voltage_v", "voltage", "measurement", "V"

    def __init__(
        self,
        key: str,
        device_class: str | None = None,
        state_class: str | None = None,
        unit_of_measurement: str | None = None,
    ):
        super().__init__(key, HomeAssistantType.SENSOR,
                         device_class, state_class, unit_of_measurement)


class HomeAssistantEntity(HomeAssistantBaseModel):
    name: str
    device: HomeAssistantDevice
    _icon: str | None = None
    _additional_fields: dict[str, any] = {}
    path: list[str] | None = Field(None, exclude=True)
    ha_type: HomeAssistantEntityBaseType = Field(
        exclude=True)
    unit: str | None = Field(None, exclude=True)

    def __init__(self, device: HomeAssistantDevice, icon: str | None = None, **data):
        super().__init__(client_id=device.client_id, device=device, **data)

        for field in self.ha_type.typed.additional_fields:
            if field in data and data[field] is not None:
                self._additional_fields[field] = data[field]

        self._icon = icon

    @computed_field
    @property
    def unique_id(self) -> str:
        return self.hash_unique_id(
            [self.device.identifiers, self.name,
                self.state_topic, self.value_template]
        )

    @computed_field
    @property
    def command_topic(self) -> str | None:
        return (
            f"{self.device.state_topic}/{'/'.join(self.path)}"
            if self.ha_type.typed.command_topic
            else None
        )

    @computed_field
    @property
    def state_topic(self) -> str:
        return self.device.state_topic

    @computed_field
    @property
    def value_template(self) -> str | None:
        return f"{{{{ value_json.{'.'.join(self.path)} }}}}" if self.path else None

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
    def payload_on(self) -> bool | None:
        return True if self.ha_type.typed == HomeAssistantType.BINARY_SENSOR else None

    @computed_field
    @property
    def payload_off(self) -> bool | None:
        return False if self.ha_type.typed == HomeAssistantType.BINARY_SENSOR else None

    @computed_field
    @property
    def icon(self) -> str | None:
        return f"mdi:{self._icon}" if self._icon else None

    def model_dump_json(self, **kwargs) -> str:
        dumped_model = super().model_dump(**kwargs)
        dumped_model = {**dumped_model, **self._additional_fields}
        return json.dumps(dumped_model)
