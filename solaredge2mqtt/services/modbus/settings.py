from pydantic import BaseModel, Field

from solaredge2mqtt.core.models import EnumModel


class AdvancedControlsSettings(EnumModel):
    ENABLED = "enabled"
    DISABLED = "disabled"
    DISABLE = "disable"


class ModbusSettings(BaseModel):
    host: str
    port: int = Field(1502)
    timeout: int = Field(1)
    unit: int = Field(1)
    check_grid_status: bool = Field(False)
    advanced_power_controls: AdvancedControlsSettings = Field(
        AdvancedControlsSettings.DISABLED)

    @property
    def advanced_power_controls_enabled(self) -> bool:
        return self.advanced_power_controls == AdvancedControlsSettings.ENABLED
