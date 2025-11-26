"""Storage control model for battery management via modbus."""

from typing import ClassVar

from pydantic import Field

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.modbus.sunspec.values import (
    STORAGE_AC_CHARGE_POLICY_MAP,
    STORAGE_CONTROL_MODE_MAP,
    STORAGE_DEFAULT_MODE_MAP,
)


class StorageControl(Solaredge2MQTTBaseModel):
    """Model for storage control status read from modbus."""

    COMPONENT: ClassVar[str] = "storage_control"
    SOURCE: ClassVar[str] = "modbus"

    control_mode: int | None = Field(
        None, title="Control mode", json_schema_extra={"input_field": None}
    )
    control_mode_text: str | None = Field(
        None, title="Control mode text", json_schema_extra={"input_field": None}
    )
    ac_charge_policy: int | None = Field(
        None, title="AC charge policy", json_schema_extra={"input_field": None}
    )
    ac_charge_policy_text: str | None = Field(
        None, title="AC charge policy text", json_schema_extra={"input_field": None}
    )
    ac_charge_limit: float | None = Field(
        None, title="AC charge limit", json_schema_extra={"input_field": None}
    )
    backup_reserve: float | None = Field(
        None,
        title="Backup reserve",
        json_schema_extra={"input_field": "backup_reserve"},
    )
    default_mode: int | None = Field(
        None,
        title="Default mode",
        json_schema_extra={"input_field": "default_mode"},
    )
    default_mode_text: str | None = Field(
        None, title="Default mode text", json_schema_extra={"input_field": None}
    )
    command_timeout: int | None = Field(
        None,
        title="Command timeout",
        json_schema_extra={"input_field": "command_timeout"},
    )
    command_mode: int | None = Field(
        None, title="Command mode", json_schema_extra={"input_field": None}
    )
    charge_limit: float | None = Field(
        None,
        title="Charge limit",
        json_schema_extra={"input_field": "charge_limit"},
    )
    discharge_limit: float | None = Field(
        None,
        title="Discharge limit",
        json_schema_extra={"input_field": "discharge_limit"},
    )

    def __init__(self, data: dict[str, int | float | None] | None = None, **kwargs):
        if data is not None:
            values = self._parse_data(data)
            super().__init__(**values)
        else:
            super().__init__(**kwargs)

    def _parse_data(self, data: dict[str, int | float | None]) -> dict:
        """Parse raw modbus data into model fields."""
        values = {}

        # Control mode
        control_mode = data.get("control_mode")
        if control_mode is not None:
            values["control_mode"] = int(control_mode)
            values["control_mode_text"] = STORAGE_CONTROL_MODE_MAP.get(
                int(control_mode), "Unknown"
            )

        # AC charge policy
        ac_charge_policy = data.get("ac_charge_policy")
        if ac_charge_policy is not None:
            values["ac_charge_policy"] = int(ac_charge_policy)
            values["ac_charge_policy_text"] = STORAGE_AC_CHARGE_POLICY_MAP.get(
                int(ac_charge_policy), "Unknown"
            )

        # AC charge limit
        ac_charge_limit = data.get("ac_charge_limit")
        if ac_charge_limit is not None:
            values["ac_charge_limit"] = round(float(ac_charge_limit), 2)

        # Backup reserve
        backup_reserve = data.get("backup_reserve")
        if backup_reserve is not None:
            values["backup_reserve"] = round(float(backup_reserve), 2)

        # Default mode
        default_mode = data.get("default_mode")
        if default_mode is not None:
            values["default_mode"] = int(default_mode)
            values["default_mode_text"] = STORAGE_DEFAULT_MODE_MAP.get(
                int(default_mode), "Unknown"
            )

        # Command timeout
        command_timeout = data.get("command_timeout")
        if command_timeout is not None:
            values["command_timeout"] = int(command_timeout)

        # Command mode
        command_mode = data.get("command_mode")
        if command_mode is not None:
            values["command_mode"] = int(command_mode)

        # Charge limit
        charge_limit = data.get("charge_limit")
        if charge_limit is not None:
            values["charge_limit"] = round(float(charge_limit), 2)

        # Discharge limit
        discharge_limit = data.get("discharge_limit")
        if discharge_limit is not None:
            values["discharge_limit"] = round(float(discharge_limit), 2)

        return values

    @property
    def is_remote_control_mode(self) -> bool:
        """Check if storage is in remote control mode (mode 4)."""
        return self.control_mode == 4

    @property
    def is_valid(self) -> bool:
        """Check if storage control data is valid."""
        return self.control_mode is not None

    @classmethod
    def generate_topic_prefix(cls, unit_key: str | None = None) -> str:
        """Generate MQTT topic prefix for storage control."""
        topic_parts = [cls.SOURCE]

        if unit_key:
            topic_parts.append(unit_key)

        topic_parts.append(cls.COMPONENT)

        return "/".join(topic_parts)

    def mqtt_topic(
        self, has_followers: bool = False, unit_key: str | None = None
    ) -> str:
        """Generate MQTT topic for storage control."""
        return self.generate_topic_prefix(unit_key if has_followers else None)

    def homeassistant_device_info(
        self, name: str = "Storage Control"
    ) -> dict[str, any]:
        """Generate Home Assistant device info."""
        return self._default_homeassistant_device_info(name)
