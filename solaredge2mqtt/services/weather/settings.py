from pydantic import BaseModel, Field, SecretStr


class WeatherSettings(BaseModel):
    api_key: SecretStr | None = Field(None)
    language: str = Field("en")

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None
