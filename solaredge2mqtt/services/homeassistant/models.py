from __future__ import annotations

import base64
import hashlib
import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, PrivateAttr, computed_field

from solaredge2mqtt.core.models import (
    BaseField,
    BaseInputScalarField,
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


class HomeAssistantStatusInput(BaseInputScalarField):
    status: HomeAssistantStatus


class HomeAssistantBaseModel(BaseModel):
    client_id: str = Field(..., exclude=True)

    def hash_unique_id(self, ids: list[str] | list[str | int]) -> str:
        ids.append(self.client_id)
        unique_id = "_".join([str(id) for id in ids])

        hash_obj = hashlib.sha256(unique_id.encode())
        hash_digest = hash_obj.digest()

        base64_encoded = base64.urlsafe_b64encode(hash_digest).decode()

        return base64_encoded[:10]


class HomeAssistantDevice(HomeAssistantBaseModel):
    name: str
    state_topic: str = Field(exclude=True)
    availability_topic: str | None = Field(default=None, exclude=True)
    manufacturer: str | None = Field(default=None)
    model: str | None = Field(default=None)
    hw_version: str | None = Field(default=None)
    serial_number: str | None = Field(default=None)
    sw_version: str | None = Field(default=None)
    via_device: str | None = Field(default=None)
    unit_key: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def identifiers(self) -> str:
        identifiers = [self.name, self.manufacturer, self.model, self.serial_number]

        if self.unit_key:
            identifiers.append(self.unit_key)

        return self.hash_unique_id(identifiers)


class HomeAssistantType(EnumModel):
    BINARY_SENSOR = "binary_sensor", False, []
    NUMBER = "number", True, ["min", "max", "step", "mode"]
    SELECT = "select", True, ["options"]
    SENSOR = "sensor", False, []

    def __init__(
        self, identifier: str, command_topic: bool, additional_fields: list[str]
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
        input_field: BaseInputFieldEnumModel | None = None,
        **json_schema_extra: Any,
    ) -> dict[str, Any]:

        json_schema_extra = {
            "ha_type": self,
            "ha_typed": self.typed.identifier,
            "icon": None,
            **json_schema_extra,
        }

        return super().field(title, input_field, **json_schema_extra)


class HomeAssistantBinarySensorType(HomeAssistantEntityBaseType):
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
    """Generic writable-number presentation.

    Deliberately holds no domain-specific members — device_class,
    unit_of_measurement, min/max/step/mode are all supplied per call site via
    field(), so callers don't need to register a new enum member here for
    every numeric config value a service happens to expose. Keeps SolarEdge
    (or any other domain's) presentation metadata in that domain's own
    module instead of leaking into this generic HA layer.
    """

    GENERIC = "number", None, None, None, None, None, None

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
        super().__init__(
            key, HomeAssistantType.NUMBER, device_class, None, unit_of_measurement
        )

        self._min: int | float | None = min
        self._max: int | float | None = max
        self._step: int | float | None = step
        self._mode: str | None = mode

    def field(
        self,
        title: str | None = None,
        input_field: BaseInputFieldEnumModel | None = None,
        **json_schema_extra: Any,
    ) -> dict[str, Any]:

        json_schema_extra = {
            "min": self._min,
            "max": self._max,
            "step": self._step,
            "mode": self._mode,
            **json_schema_extra,
        }

        return super().field(
            title,
            input_field,
            **json_schema_extra,
        )


class HomeAssistantSelectType(HomeAssistantEntityBaseType):
    """Generic writable-select presentation.

    Like HomeAssistantNumberType, holds no domain-specific members: the
    options map (raw value -> human label) is supplied per call site via
    field(options_map=...), not baked into an enum member here. The map
    itself flows through to HomeAssistantEntity via json_schema_extra and
    drives its value_template/command_template — this class only knows how
    to render "a select with an optional label mapping", never what any
    particular domain's labels actually are.
    """

    GENERIC = "select", None, None, None

    def __init__(
        self,
        key: str,
        device_class: str | None = None,
        state_class: str | None = None,
        unit_of_measurement: str | None = None,
    ):
        super().__init__(
            key,
            HomeAssistantType.SELECT,
            device_class,
            state_class,
            unit_of_measurement,
        )

    def field(
        self,
        title: str | None = None,
        input_field: BaseInputFieldEnumModel | None = None,
        options_map: dict[Any, Any] | None = None,
        **json_schema_extra: Any,
    ) -> dict[str, Any]:

        json_schema_extra = {
            "options": list(options_map.values()) if options_map else [],
            "options_map": options_map,
            **json_schema_extra,
        }

        return super().field(
            title,
            input_field,
            **json_schema_extra,
        )


class HomeAssistantSensorType(HomeAssistantEntityBaseType):
    APPARENT_POWER = "apparent_power", "apparent_power", "measurement", "VA"
    BATTERY = "battery", "battery", "measurement", "%"
    CURRENT_A = "current_a", "current", "measurement", "A"
    ENERGY_KWH = "energy_kwh", "energy", "total_increasing", "kWh"
    ENERGY_WH = (
        "energy_wh",
        "energy",
        "total_increasing",
        "Wh",
    )
    ENERGY_MEASUREMENT_WH = "energy_measurement_wh", "energy", "measurement", "Wh"
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
    TIMESTAMP = "timestamp", "timestamp", None, None
    VOLTAGE_V = "voltage_v", "voltage", "measurement", "V"

    def __init__(
        self,
        key: str,
        device_class: str | None = None,
        state_class: str | None = None,
        unit_of_measurement: str | None = None,
    ):
        super().__init__(
            key,
            HomeAssistantType.SENSOR,
            device_class,
            state_class,
            unit_of_measurement,
        )


def _jinja_dict_literal(mapping: dict[Any, Any]) -> str:
    items = ", ".join(f"{key!r}: {value!r}" for key, value in mapping.items())
    return f"{{{items}}}"


class HomeAssistantEntity(HomeAssistantBaseModel):
    name: str
    device: HomeAssistantDevice

    path: list[str] | None = Field(None, exclude=True)
    ha_type: HomeAssistantEntityBaseType = Field(exclude=True)
    unit: str | None = Field(None, exclude=True)
    device_class_override: str | None = Field(None, exclude=True)
    command_topic_override: str | None = Field(None, exclude=True)
    options_map: dict[Any, Any] | None = Field(None, exclude=True)

    _icon: str | None = PrivateAttr(default=None)
    _additional_fields: dict[str, Any] = PrivateAttr(default_factory=dict)

    def __init__(self, device: HomeAssistantDevice, icon: str | None = None, **data):
        super().__init__(client_id=device.client_id, **{"device": device, **data})

        for field in self.ha_type.typed.additional_fields:
            if field in data and data[field] is not None:
                self._additional_fields[field] = data[field]

        self._icon = icon

    @computed_field
    @property
    def unique_id(self) -> str:
        ids = [self.device.identifiers, self.name, self.state_topic]

        if value_template := self.value_template:
            ids.append(value_template)

        return self.hash_unique_id(ids)

    @computed_field
    @property
    def command_topic(self) -> str | None:
        if not self.ha_type.typed.command_topic:
            return None

        if self.command_topic_override:
            return f"{self.device.state_topic}/{self.command_topic_override}"

        path = [self.device.state_topic]

        if self.path:
            path.extend(self.path)

        return "/".join(path)

    @computed_field
    @property
    def state_topic(self) -> str:
        return self.device.state_topic

    @computed_field
    @property
    def availability_topic(self) -> str | None:
        return self.device.availability_topic

    @computed_field
    @property
    def value_template(self) -> str | None:
        if not self.path:
            return None

        value_expr = f"value_json.{'.'.join(self.path)}"

        if self.options_map:
            # options_map keys are stringified by pydantic's JSON-schema
            # serialization (json_schema_extra round-trips through
            # model_json_schema), even though the raw MQTT payload holds a
            # real int. Normalize both sides to string so the lookup matches.
            mapping = _jinja_dict_literal(
                {str(code): label for code, label in self.options_map.items()}
            )
            value_expr = f"{mapping}[({value_expr}) | string]"

        return f"{{{{ {value_expr} }}}}"

    @computed_field
    @property
    def command_template(self) -> str | None:
        if not self.options_map:
            return None

        reverse_map = {label: str(code) for code, label in self.options_map.items()}
        mapping = _jinja_dict_literal(reverse_map)
        return f"{{{{ {mapping}[value] }}}}"

    @computed_field
    @property
    def state_class(self) -> str | None:
        return self.ha_type.state_class

    @computed_field
    @property
    def device_class(self) -> str | None:
        if self.device_class_override is not None:
            return self.device_class_override

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
