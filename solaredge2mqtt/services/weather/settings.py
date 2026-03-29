from pydantic import BaseModel, Field, SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException


class WeatherSettings(BaseModel):
    api_key: SecretStr | None = Field(default=None)
    language: str = Field(default="en")
    retain: bool = Field(default=False)

    @property
    def api_key_secret(self) -> str:
        if self.api_key is None:
            raise ConfigurationException("weather", "Weather service has no api key.")

        return self.api_key.get_secret_value()

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None and bool(self.api_key_secret)
