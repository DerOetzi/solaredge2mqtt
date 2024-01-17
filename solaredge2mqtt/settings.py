from __future__ import annotations

from functools import lru_cache
from os import path
from time import localtime, strftime
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from solaredge2mqtt.logging import LoggingLevelEnum

DOCKER_SECRETS_DIR = "/run/secrets"

MODEL_CONFIG_WITHOUT_SECRETS = {
    "env_file": ".env",
    "env_prefix": "se2mqtt_",
    "env_nested_delimiter": "__",
}

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
SECONDS_PER_HOUR = 3600
SECONDS_PER_YEAR = SECONDS_PER_DAY * 365
SECONDS_PER_2_YEARS = SECONDS_PER_YEAR * 2


class ModbusSettings(BaseModel):
    host: str
    port: int = Field(1502)
    timeout: int = Field(1)
    unit: int = Field(1)


class MQTTSettings(BaseModel):
    client_id: str = Field("solaredge2mqtt")
    broker: str
    port: int = Field(1883)
    username: str
    password: str
    topic_prefix: str = Field("solaredge")


class MonitoringSettings(BaseModel):
    site_id: str = Field(None)
    username: str = Field(None)
    password: str = Field(None)

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.site_id is not None,
                self.username is not None,
                self.password is not None,
            ]
        )


class WallboxSettings(BaseModel):
    host: str = Field(None)
    password: str = Field(None)
    serial: str = Field(None)

    @property
    def is_configured(self) -> bool:
        return all(
            [self.host is not None, self.password is not None, self.serial is not None]
        )


class ForecastSettings(BaseModel):
    latitude: str = Field(None)
    longitude: str = Field(None)
    api_key: Optional[str] = Field(None)

    string1: ForecastStringSettings = Field(None)
    string2: ForecastStringSettings = Field(None)

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.latitude is not None,
                self.longitude is not None,
                self.string1 is not None,
            ]
        )


class ForecastStringSettings(BaseModel):
    declination: float = Field(None)
    azimuth: float = Field(None)
    peak_power: float = Field(None)

    @property
    def url_string(self) -> str:
        return f"/{self.declination}/{self.azimuth}/{self.peak_power}"


class InfluxDBSettings(BaseModel):
    host: str = Field(None)
    port: int = Field(8086)
    token: str = Field(None)
    org: str = Field(None)
    prefix: str = Field("solaredge")
    retention_raw: int = Field(SECONDS_PER_DAY + SECONDS_PER_HOUR)
    retention_aggregated: int = Field(SECONDS_PER_2_YEARS)
    aggregate_interval: str = "10m"
    timezone: str = Field(strftime("%Z", localtime()))

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.host is not None,
                self.port is not None,
                self.token is not None,
                self.org is not None,
            ]
        )


class ServiceSettings(BaseSettings):
    environment: str = "production"
    interval: int = Field(5)
    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    modbus: ModbusSettings
    mqtt: MQTTSettings

    monitoring: Optional[MonitoringSettings] = None
    wallbox: Optional[WallboxSettings] = None

    influxdb: Optional[InfluxDBSettings] = None

    forecast: Optional[ForecastSettings] = None

    model_config = MODEL_CONFIG

    @property
    def is_monitoring_configured(self) -> bool:
        return self.monitoring is not None and self.monitoring.is_configured

    @property
    def is_wallbox_configured(self) -> bool:
        return self.wallbox is not None and self.wallbox.is_configured

    @property
    def is_influxdb_configured(self) -> bool:
        return self.influxdb is not None and self.influxdb.is_configured

    @property
    def is_forecast_configured(self) -> bool:
        return self.forecast is not None and self.forecast.is_configured


@lru_cache()
def service_settings() -> ServiceSettings:
    return ServiceSettings()
