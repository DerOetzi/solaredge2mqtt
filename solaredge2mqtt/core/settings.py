from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from solaredge2mqtt.core.logging import LoggingLevelEnum
from solaredge2mqtt.models.base import EnumModel


class ServiceSettings(BaseSettings):
    debug: bool = Field(False)

    environment: str = "production"

    modbus_host: str = Field("127.0.0.1")
    modbus_port: int = Field(1502)
    modbus_timeout: int = Field(1)
    modbus_unit: int = Field(1)

    interval: int = Field(10)

    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="se2mqtt_",
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
