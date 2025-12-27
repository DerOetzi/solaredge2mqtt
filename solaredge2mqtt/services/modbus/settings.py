from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from solaredge2mqtt.core.models import EnumModel
from solaredge2mqtt.services.modbus.models.base import ModbusUnitRole


class AdvancedControlsSettings(EnumModel):
    ENABLED = "enabled"
    DISABLED = "disabled"
    DISABLE = "disable"


class ModbusUnitSettings(BaseModel):
    unit: int = Field(1)
    meter: list[bool] = Field(default_factory=list)
    battery: list[bool] = Field(default_factory=list)
    role: ModbusUnitRole = Field(ModbusUnitRole.LEADER, read_only=True)

    @model_validator(mode='before')
    @classmethod
    def fill_defaults(cls, values: dict) -> dict:
        values = cls._fill_defaults_array("meter", values, 3)
        values = cls._fill_defaults_array("battery", values, 2)

        return values

    @staticmethod
    def _fill_defaults_array(
        key: str, values: dict, length: int, default: str = "true"
    ) -> dict:
        if key not in values or not isinstance(values[key], list):
            values[key] = [default] * length
        else:
            for i, value in enumerate(values[key][:length]):
                if isinstance(value, str):
                    values[key][i] = value.lower() == "true"
                elif isinstance(value, bool):
                    values[key][i] = value
                else:
                    values[key][i] = default.lower() == "true"

            if len(values[key]) < length:
                values[key].extend([default] * (length - len(values[key])))

        return values


class ModbusSettings(ModbusUnitSettings):
    host: str = Field(None)
    port: int = Field(1502)

    timeout: int = Field(1)

    check_grid_status: bool = Field(False)
    advanced_power_controls: AdvancedControlsSettings = Field(
        AdvancedControlsSettings.DISABLED)

    follower: list[ModbusUnitSettings] = Field(default_factory=list)

    retain: bool = Field(False)

    @model_validator(mode='before')
    @classmethod
    def fill_defaults(cls, values: dict) -> dict:
        values = super().fill_defaults(values)

        for i, slave_values in enumerate(values.get("follower", [])):
            slave_values["role"] = ModbusUnitRole.FOLLOWER
            slave_values = super()._fill_defaults_array(
                "meter", slave_values, 3, "false"
            )
            slave_values = super()._fill_defaults_array(
                "battery", slave_values, 2, "false"
            )
            values["follower"][i] = slave_values

        return values

    @property
    def advanced_power_controls_enabled(self) -> bool:
        return self.advanced_power_controls == AdvancedControlsSettings.ENABLED

    @property
    def units(self) -> dict[str, ModbusUnitSettings]:
        units = {"leader": self}
        for i, follower in enumerate(self.follower):
            units[f"follower{i}"] = follower

        return units

    @property
    def has_followers(self) -> bool:
        return len(self.follower) > 0
