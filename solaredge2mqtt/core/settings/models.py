from os import environ, listdir, path
from typing import Generator

from pydantic import BaseModel, Field

from solaredge2mqtt.core.influxdb.settings import InfluxDBSettings
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.logging.models import LoggingLevelEnum
from solaredge2mqtt.core.mqtt.settings import MQTTSettings
from solaredge2mqtt.services.energy.settings import EnergySettings, PriceSettings
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.homeassistant.settings import HomeAssistantSettings
from solaredge2mqtt.services.modbus.settings import ModbusSettings
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings
from solaredge2mqtt.services.powerflow.settings import PowerflowSettings
from solaredge2mqtt.services.wallbox.settings import WallboxSettings
from solaredge2mqtt.services.weather.settings import WeatherSettings

DOCKER_SECRETS_DIR = "/run/secrets"


class LocationSettings(BaseModel):
    latitude: float
    longitude: float


class ServiceSettings(BaseModel):
    interval: int = Field(5)
    logging_level: LoggingLevelEnum = LoggingLevelEnum.INFO

    modbus: ModbusSettings
    mqtt: MQTTSettings

    powerflow: PowerflowSettings = PowerflowSettings()
    energy: EnergySettings = EnergySettings()

    location: LocationSettings | None = None
    prices: PriceSettings = PriceSettings()

    monitoring: MonitoringSettings | None = None
    wallbox: WallboxSettings | None = None

    influxdb: InfluxDBSettings | None = None

    weather: WeatherSettings | None = None

    forecast: ForecastSettings | None = None

    homeassistant: HomeAssistantSettings | None = None

    def __init__(self, **data: dict[str, any]):
        sources = [self._read_environment,
                   self._read_dotenv, self._read_secrets]
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

    @property
    def is_homeassistant_configured(self) -> bool:
        return self.homeassistant is not None and self.homeassistant.is_configured

    def _parse_key_and_values(
        self, sources: list[callable], data: dict[str, any]
    ) -> dict[str, any]:
        for source in sources:
            for key, value in source():
                key = key.lower().strip()[8:]
                subkeys = key.split("__")
                self.insert_nested_key(
                    data, subkeys, value.strip())

        return data

    @classmethod
    def insert_nested_key(cls, container: dict, keys: list[str], value: any) -> None:
        key, i = cls._identify_key_and_position(keys)

        key, idx, next_container = cls._get_or_initialize_nested_container(
            container, key, i
        )

        cls._insert_value_in_container(
            container, keys, value, key, idx, next_container)

    @classmethod
    def _identify_key_and_position(cls, keys: list[str]) -> tuple[str, int]:
        key = keys[0]
        for i in range(len(key) - 1, -1, -1):
            if not key[i].isdigit():
                break
        return key, i

    @classmethod
    def _get_or_initialize_nested_container(
        cls, container: dict, key: str, i: int
    ) -> tuple[str, int | str, dict | list]:
        prefix, idx = key[:i + 1], key[i + 1:]
        if idx.isdigit():
            key, idx = prefix, int(idx)
            if key not in container or not isinstance(container[key], list):
                container[key] = []
            while len(container[key]) <= idx:
                container[key].append({})
            next_container = container[key][idx]
        else:
            if key not in container or not isinstance(container[key], dict):
                container[key] = {}
            next_container = container[key]
        return key, idx, next_container

    @classmethod
    def _insert_value_in_container(
        cls,
        container: dict[str, any],
        keys: list[str],
        value: any,
        key: str,
        idx: int | str,
        next_container: dict | list,
    ) -> None:
        if len(keys) == 1:
            if isinstance(next_container, dict):
                if isinstance(container[key], list):
                    container[key][idx] = value
                else:
                    container[key] = value
            else:
                container[key] = value
        else:
            cls.insert_nested_key(next_container, keys[1:], value)

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
