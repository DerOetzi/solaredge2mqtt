from os import path

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from solaredge2mqtt.logging import LoggingLevelEnum
from solaredge2mqtt.models import EnumModel

DOCKER_SECRETS_DIR = "/run/secrets"

MODEL_CONFIG_WITHOUT_SECRETS = {"env_file": ".env", "env_prefix": "se2mqtt_"}

MODEL_CONFIG_WITH_SECRETS = {
    **MODEL_CONFIG_WITHOUT_SECRETS,
    "secrets_dir": DOCKER_SECRETS_DIR,
}

MODEL_CONFIG = (
    SettingsConfigDict(**MODEL_CONFIG_WITH_SECRETS)
    if path.exists(DOCKER_SECRETS_DIR)
    else SettingsConfigDict(**MODEL_CONFIG_WITHOUT_SECRETS)
)


SECONDS_PER_DAY = 86400
SECONDS_PER_YEAR = SECONDS_PER_DAY * 365
SECONDS_PER_2_YEARS = SECONDS_PER_YEAR * 2


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

    wallbox_host: Optional[str] = Field(None)
    wallbox_password: Optional[str] = Field(None)
    wallbox_serial: Optional[str] = Field(None)

    influxdb_host: Optional[str] = Field(None)
    influxdb_port: Optional[int] = Field(8086)
    influxdb_token: Optional[str] = Field(None)
    influxdb_org: Optional[str] = Field(None)
    influxdb_prefix: Optional[str] = Field("solaredge")
    influxdb_retention_raw: Optional[int] = Field(SECONDS_PER_DAY)
    influxdb_retention_aggregated: Optional[int] = Field(SECONDS_PER_2_YEARS)

    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    model_config = MODEL_CONFIG

    @property
    def is_api_configured(self) -> bool:
        return all(
            [
                self.api_site_id is not None,
                self.api_username is not None,
                self.api_password is not None,
            ]
        )

    @property
    def is_wallbox_configured(self) -> bool:
        return all(
            [
                self.wallbox_host is not None,
                self.wallbox_password is not None,
                self.wallbox_serial is not None,
            ]
        )

    @property
    def is_influxdb_configured(self) -> bool:
        return all(
            [
                self.influxdb_host is not None,
                self.influxdb_port is not None,
                self.influxdb_token is not None,
                self.influxdb_org is not None,
            ]
        )


class DevelopmentSettings(ServiceSettings):
    debug: bool = Field(True)

    environment: str = "development"

    influxdb_prefix: Optional[str] = Field("solaredgedev")

    model_config = MODEL_CONFIG


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

    model_config = SettingsConfigDict(**MODEL_CONFIG_WITHOUT_SECRETS, extra="ignore")


def service_settings() -> ServiceSettings:
    environment = ServiceBaseSettings().environment
    return environment.settings_class()
