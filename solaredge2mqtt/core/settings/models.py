from pydantic import BaseModel, Field

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
                "Weather settings are configured but location is not "
                "configured."
            )
            is_configured = False

        return is_configured

    @property
    def is_forecast_configured(self) -> bool:
        is_configured = (
            self.forecast is not None and self.forecast.is_configured
        )

        if is_configured and not self.is_location_configured:
            logger.warning(
                "Forecast settings are configured but location is not "
                "configured."
            )
            is_configured = False

        if is_configured and not self.is_weather_configured:
            logger.warning(
                "Forecast settings are configured but weather is not "
                "configured."
            )
            is_configured = False

        return is_configured

    @property
    def is_homeassistant_configured(self) -> bool:
        return (
            self.homeassistant is not None
            and self.homeassistant.is_configured
        )
