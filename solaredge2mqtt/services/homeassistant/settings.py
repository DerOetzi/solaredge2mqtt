from pydantic import BaseModel, Field


class HomeAssistantSettings(BaseModel):
    enable: bool = Field(default=False)
    topic_prefix: str = Field(default="homeassistant")
    retain: bool = Field(default=False)
