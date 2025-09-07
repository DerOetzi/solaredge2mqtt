from pydantic import BaseModel, Field


class HomeAssistantSettings(BaseModel):
    enable: bool = Field(False)
    topic_prefix: str = Field("homeassistant")
    retain: bool = Field(False)

    @property
    def is_configured(self) -> bool:
        return self.enable
