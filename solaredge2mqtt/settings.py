from __future__ import annotations

from functools import lru_cache
from os import environ, listdir, path
from time import localtime, strftime
from typing import Generator

from pydantic import BaseModel, Field, SecretStr

from solaredge2mqtt.logging import LoggingLevelEnum, logger

DOCKER_SECRETS_DIR = "/run/secrets"

SECONDS_PER_DAY = 86400
SECONDS_PER_HOUR = 3600
SECONDS_PER_YEAR = SECONDS_PER_DAY * 365
SECONDS_PER_2_YEARS = SECONDS_PER_YEAR * 2

LOCAL_TZ = strftime("%Z", localtime())


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


class InfluxDBSettings(BaseModel):
    host: str = Field(None)
    port: int = Field(8086)
    token: SecretStr = Field(None)
    org: str = Field(None)
    bucket: str = Field("solaredge")
    retention: int = Field(SECONDS_PER_2_YEARS)
    retention_raw: int = Field(25)

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


class PriceSettings(BaseModel):
    consumption: float = Field(None)
    delivery: float = Field(None)

    @property
    def is_configured(self) -> bool:
        return self.is_consumption_configured or self.is_delivery_configured

    @property
    def is_consumption_configured(self) -> bool:
        return self.consumption is not None

    @property
    def is_delivery_configured(self) -> bool:
        return self.delivery is not None

    @property
    def price_in(self) -> float:
        return self.consumption or 0.0

    @property
    def price_out(self) -> float:
        return self.delivery or 0.0


class LocationSettings(BaseModel):
    latitude: float
    longitude: float


class WeatherSettings(BaseModel):
    api_key: SecretStr | None = Field(None)
    language: str = Field("en")

    @property
    def is_configured(self) -> bool:
        return self.api_key is not None


class ForecastSettings(BaseModel):
    enable: bool = Field(False)
    hyperparametertuning: bool = Field(False)

    @property
    def is_configured(self) -> bool:
        return self.enable


class ServiceSettings(BaseModel):
    interval: int = Field(5)
    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    modbus: ModbusSettings
    mqtt: MQTTSettings

    location: LocationSettings | None = None
    prices: PriceSettings = PriceSettings()

    monitoring: MonitoringSettings | None = None
    wallbox: WallboxSettings | None = None

    influxdb: InfluxDBSettings | None = None

    weather: WeatherSettings | None = None

    forecast: ForecastSettings | None = None

    def __init__(self, **data: dict[str, any]):
        sources = [self._read_environment, self._read_dotenv, self._read_secrets]
        data = self._parse_key_and_values(sources, data)
        super().__init__(**data)

    @property
    def is_location_configured(self) -> bool:
        return self.location is not None

    @property
    def is_prices_configured(self) -> bool:
        return self.prices is not None and self.prices.is_configured

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
    def is_weather_configured(self) -> bool:
        is_configured = self.weather is not None and self.weather.is_configured

        if is_configured and not self.is_location_configured:
            logger.warning(
                "Weather settings are configured but location is not configured."
            )
            is_configured = False

        return is_configured

    @property
    def is_forecast_configured(self) -> bool:
        is_configured = self.forecast is not None and self.forecast.is_configured

        if is_configured and not self.is_location_configured:
            logger.warning(
                "Forecast settings are configured but location is not configured."
            )
            is_configured = False

        if is_configured and not self.is_weather_configured:
            logger.warning(
                "Forecast settings are configured but weather is not configured."
            )
            is_configured = False

        return is_configured

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

                context[subkeys[-1]] = (
                    value.strip()
                )  # Missing possibility to set nested json values

        return data

    @classmethod
    def _read_environment(cls) -> Generator[tuple[str, str], any, any]:
        for key, value in environ.items():
            if cls._has_prefix(key):
                yield key, value

    @classmethod
    def _read_secrets(cls) -> Generator[tuple[str, str], any, any]:
        if path.exists(DOCKER_SECRETS_DIR) and path.isdir(DOCKER_SECRETS_DIR):
            for filename in listdir(DOCKER_SECRETS_DIR):
                if cls._has_prefix(filename):
                    with open(
                        path.join(DOCKER_SECRETS_DIR, filename), "r", encoding="utf-8"
                    ) as f:
                        yield filename, f.read()

    @classmethod
    def _read_dotenv(cls) -> Generator[tuple[str, str], any, any]:
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
