from __future__ import annotations

from functools import lru_cache
from os import environ, path, listdir
from time import localtime, strftime
from typing import Optional

from pydantic import BaseModel, Field, SecretStr

from solaredge2mqtt.logging import LoggingLevelEnum

DOCKER_SECRETS_DIR = "/run/secrets"

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
    password: SecretStr
    topic_prefix: str = Field("solaredge")


class MonitoringSettings(BaseModel):
    site_id: str = Field(None)
    username: str = Field(None)
    password: SecretStr = Field(None)

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
    password: SecretStr = Field(None)
    serial: str = Field(None)

    @property
    def is_configured(self) -> bool:
        return all(
            [self.host is not None, self.password is not None, self.serial is not None]
        )


class ForecastSettings(BaseModel):
    latitude: str = Field(None)
    longitude: str = Field(None)
    api_key: Optional[SecretStr] = Field(None)

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
    token: SecretStr = Field(None)
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


class ServiceSettings(BaseModel):
    interval: int = Field(5)
    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    modbus: ModbusSettings
    mqtt: MQTTSettings

    monitoring: Optional[MonitoringSettings] = None
    wallbox: Optional[WallboxSettings] = None

    influxdb: Optional[InfluxDBSettings] = None

    forecast: Optional[ForecastSettings] = None

    def __init__(self, **data: dict[str, any]):
        sources = [self._read_environment, self._read_dotenv, self._read_secrets]
        data = self._parse_key_and_values(sources, data)
        super().__init__(**data)

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

    def _parse_key_and_values(
        self, sources: list[callable], data: dict[str, any]
    ) -> dict[str, any]:
        for source in sources:
            for key, value in source():
                key = key.lower().strip()[8:]  # remove prefix
                subkeys = key.split("__")  # get nested structure
                context = data
                for subkey in subkeys[:-1]:
                    if subkey not in context:
                        context[subkey] = {}
                    context = context[subkey]

                context[
                    subkeys[-1]
                ] = value.strip()  # Missing possibility to set nested json values

        return data

    @classmethod
    def _read_environment(cls) -> tuple[str, str]:
        for key, value in environ.items():
            if cls._has_prefix(key):
                yield key, value

    @classmethod
    def _read_secrets(cls) -> tuple[str, str]:
        if path.exists(DOCKER_SECRETS_DIR) and path.isdir(DOCKER_SECRETS_DIR):
            for filename in listdir(DOCKER_SECRETS_DIR):
                if cls._has_prefix(filename):
                    with open(
                        path.join(DOCKER_SECRETS_DIR, filename), "r", encoding="utf-8"
                    ) as f:
                        yield filename, f.read()

    @classmethod
    def _read_dotenv(cls) -> tuple[str, str]:
        if path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if cls._has_prefix(line) and "=" in line:
                        key, value = line.split("=", 1)
                        yield key, value

    @staticmethod
    def _has_prefix(key: str) -> bool:
        return key.lower().startswith("se2mqtt_")


@lru_cache()
def service_settings() -> ServiceSettings:
    return ServiceSettings()
