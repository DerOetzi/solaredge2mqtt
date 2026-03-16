from pydantic import BaseModel, Field

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.influxdb.settings import InfluxDBSettings
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.logging.models import LoggingLevelEnum
from solaredge2mqtt.core.mqtt.settings import MQTTSettings
from solaredge2mqtt.services.energy.settings import (
    EnergySettings,
    PriceSettings,
)
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.homeassistant.settings import (
    HomeAssistantSettings,
)
from solaredge2mqtt.services.modbus.settings import ModbusSettings
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings
from solaredge2mqtt.services.powerflow.settings import PowerflowSettings
from solaredge2mqtt.services.wallbox.settings import WallboxSettings
from solaredge2mqtt.services.weather.settings import WeatherSettings


class LocationSettings(BaseModel):
    latitude: float | None = Field(default=None)
    longitude: float | None = Field(default=None)

    @property
    def latitude_value(self) -> float:
        if self.latitude is None:
            raise ConfigurationException(
                "location", "Latitude is not configured")

        return self.latitude

    @property
    def longitude_value(self) -> float:
        if self.longitude is None:
            raise ConfigurationException(
                "location", "Longitude is not configured")

        return self.longitude

    @property
    def is_configured(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class ServiceSettings(BaseModel):
    interval: int = Field(default=5)
    logging_level: LoggingLevelEnum = Field(default=LoggingLevelEnum.INFO)

    modbus: ModbusSettings
    mqtt: MQTTSettings

    powerflow: PowerflowSettings = Field(default=PowerflowSettings())
    energy: EnergySettings = Field(default=EnergySettings())

    location: LocationSettings = Field(default=LocationSettings())
    prices: PriceSettings = Field(default=PriceSettings())

    monitoring: MonitoringSettings = Field(default=MonitoringSettings())
    wallbox: WallboxSettings = Field(default=WallboxSettings())

    influxdb: InfluxDBSettings = Field(default=InfluxDBSettings())

    weather: WeatherSettings = Field(default=WeatherSettings())

    forecast: ForecastSettings = Field(default=ForecastSettings())

    homeassistant: HomeAssistantSettings = Field(
        default=HomeAssistantSettings())

    @property
    def is_weather_enabled(self) -> bool:
        if (self.weather.is_configured
                and not self.location.is_configured):
            logger.warning(
                "Weather settings are configured but location is not "
                "configured. Weather service will not be initialized."
            )

            return False

        return self.weather.is_configured

    @property
    def is_forecast_enabled(self) -> bool:
        if self.forecast.enable and not self.is_weather_enabled:
            logger.warning(
                "Forecast settings are enabled but weather service is not "
                "configured. Forecast service will not be initialized."
            )

            return False

        return self.forecast.enable
