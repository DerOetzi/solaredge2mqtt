from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from solaredge2mqtt.logging import LoggingLevelEnum
from solaredge2mqtt.models import EnumModel


class ServiceSettings(BaseSettings):
    environment: str = "production"

    modbus_host: str
    modbus_port: int = Field(1502)
    modbus_timeout: int = Field(1)
    modbus_unit: int = Field(1)

    api_site_id: Optional[str] = Field(None)
    api_username: Optional[str] = Field(None)
    api_password: Optional[str] = Field(None)

    client_id: str = Field("solaredge2mqtt")
    broker: str
    port: int = Field(1883)
    username: str
    password: str
    topic_prefix: str = Field("solaredge")

    interval: int = Field(5)

    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="se2mqtt_",
        secrets_dir="/run/secrets",
    )

    @property
    def is_api_configured(self) -> bool:
        return all(
            [
                self.api_site_id is not None,
                self.api_username is not None,
                self.api_password is not None,
            ]
        )


class DevelopmentSettings(ServiceSettings):
    debug: bool = Field(True)

    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="se2mqtt_",
    )


class ServiceEnvironment(EnumModel):
    PROD = "production", ServiceSettings
    DEV = "development", DevelopmentSettings

    def __init__(self, description: str, settings_class: ServiceSettings):
        # pylint: disable=super-init-not-called
        self._description: str = description
        self._settings_class: ServiceSettings = settings_class

    @property
    def description(self) -> str:
        return self._description

    @property
    def settings_class(self) -> ServiceSettings:
        return self._settings_class


class ServiceBaseSettings(BaseSettings):
    environment: ServiceEnvironment = ServiceEnvironment.PROD

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="se2mqtt_", extra="ignore"
    )


def service_settings() -> ServiceSettings:
    environment = ServiceBaseSettings().environment
    return environment.settings_class()
