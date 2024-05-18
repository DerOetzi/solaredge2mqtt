from pydantic import BaseModel, Field


class ForecastSettings(BaseModel):
    enable: bool = Field(False)
    hyperparametertuning: bool = Field(False)

    @property
    def is_configured(self) -> bool:
        return self.enable
