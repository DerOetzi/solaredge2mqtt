from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from solaredge2mqtt.core.models import EnumModel


class AdvancedControlsSettings(EnumModel):
    ENABLED = "enabled"
    DISABLED = "disabled"
    DISABLE = "disable"


class ModbusUnitSettings(BaseModel):
    unit: int = Field(1)
    timeout: int = Field(1)
    port: int = Field(1502)
    host: str = Field(None)
    meter: list[bool] = Field(default_factory=list)
    battery: list[bool] = Field(default_factory=list)

    @model_validator(mode='before')
    @classmethod
    def fill_defaults(cls, values: dict) -> dict:
        values = cls._fill_defaults_array("meter", values, 3)
        values = cls._fill_defaults_array("battery", values, 2)

        return values

    @staticmethod
    def _fill_defaults_array(key: str, values: dict, length: int) -> dict:
        if key not in values or not isinstance(values[key], list):
            values[key] = ["true"] * length
        else:
            values[key] = [
                "true" if not isinstance(
                    value, str) or value.lower() == "true" else "false"
                for value in values[key][:length]
            ]

            if len(values[key]) < length:
                values[key].extend(["true"] * (length - len(values[key])))

        return values


class ModbusSettings(ModbusUnitSettings):
    check_grid_status: bool = Field(False)
    advanced_power_controls: AdvancedControlsSettings = Field(
        AdvancedControlsSettings.DISABLED)

    @property
    def advanced_power_controls_enabled(self) -> bool:
        return self.advanced_power_controls == AdvancedControlsSettings.ENABLED
