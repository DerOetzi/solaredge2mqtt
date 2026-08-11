from __future__ import annotations

from asyncio import to_thread
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, cast

from pandas import DataFrame, to_datetime
from pvlearn.config import ForecasterConfig
from pvlearn.exceptions import PVLearnError
from pvlearn.forecaster import Forecaster
from pvlearn.location import Location
from tzlocal import get_localzone

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync, Point
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.forecast.models import Forecast
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.models import (
    OpenWeatherMapBaseData,
    OpenWeatherMapForecastData,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import LocationSettings


LOCAL_TZ = get_localzone()

#: Resolution of the weather forecast, the training data and the prediction.
INTERVAL_MINUTES = 60

ENERGY_FIELD = "energy"
POWER_FIELD = "power"

WH_PER_KWH = 1000


class ForecastService:
    def __init__(
        self,
        settings: ForecastSettings,
        location: LocationSettings,
        influxdb: InfluxDBAsync,
    ) -> None:
        self.settings = settings
        self.location = location

        self.influxdb = influxdb

        forecaster_location = Location(
            latitude=location.latitude_value,
            longitude=location.longitude_value,
            timezone=str(LOCAL_TZ),
        )
        forecaster_config = ForecasterConfig(
            interval_minutes=INTERVAL_MINUTES,
            hyperparametertuning=settings.hyperparametertuning,
            cachingdir=settings.cachingdir,
            cache_size_limit_mb=settings.cache_size_limit_mb,
        )
        self.forecaster = Forecaster(forecaster_location, forecaster_config)

        self.last_weather_forecast: list[OpenWeatherMapForecastData] | None = None
        self.last_hour_forecast: dict[int, OpenWeatherMapForecastData] | None = None

        self.last_battery_capacity_wh: float | None = None
        self.last_battery_stored_energy_wh: float | None = None

        EventBus.register(self)

    @EventBus.subscribe(ModbusUnitsReadEvent)
    async def battery_update(self, event: ModbusUnitsReadEvent) -> None:
        capacity_wh = 0.0
        stored_energy_wh = 0.0
        battery_found = False

        for unit in event.units.values():
            for battery in unit.batteries.values():
                capacity_wh += battery.rated_energy
                stored_energy_wh += battery.rated_energy * battery.state_of_charge / 100
                battery_found = True

        if battery_found:
            self.last_battery_capacity_wh = capacity_wh
            self.last_battery_stored_energy_wh = stored_energy_wh
        else:
            self.last_battery_capacity_wh = None
            self.last_battery_stored_energy_wh = None

    def battery_charge_needed_wh(self) -> float | None:
        if not self.last_battery_capacity_wh:
            return None

        target_energy_wh = (
            self.last_battery_capacity_wh * self.settings.battery_target_soc / 100
        )
        deficit_wh = target_energy_wh - (self.last_battery_stored_energy_wh or 0)

        if deficit_wh <= 0:
            return 0.0

        return deficit_wh / self.settings.battery_charge_efficiency

    @EventBus.subscribe(WeatherUpdateEvent)
    async def weather_update(self, event: WeatherUpdateEvent) -> None:
        self.last_weather_forecast = event.weather.hourly

        if self.last_hour_forecast is None:
            self.last_hour_forecast = {}

        self.last_hour_forecast[event.weather.hourly[0].hour] = event.weather.hourly[0]

        now = datetime.now().astimezone()
        last_hour = now - timedelta(hours=1)

        for delete_hour in range(0, 24):
            if delete_hour in [now.hour, last_hour.hour]:
                continue

            self.last_hour_forecast.pop(delete_hour, None)

        logger.debug(self.last_hour_forecast)

        if last_hour.hour in self.last_hour_forecast:
            await self.write_new_training_data(self.last_hour_forecast[last_hour.hour])

    async def write_new_training_data(
        self, last_hour_weather_forecast: OpenWeatherMapForecastData
    ) -> None:
        now = datetime.now().astimezone()
        last_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

        training_data = last_hour_weather_forecast.model_dump_estimation_data()
        training_data["time"] = last_hour
        training_data = await self.add_last_hour_pv_production(training_data)
        await self.write_new_training_data_to_influxdb(training_data)

        if (now.minute // 10) * 10 == 20:
            await self.train()

    async def add_last_hour_pv_production(
        self, trainings_data
    ) -> dict[str, str | float | int | None]:
        production_data = await self.influxdb.query_first("production")

        if production_data is None:
            raise InvalidDataException(
                "Missing production data of last hour for forecast training."
                + " Did the service write power information to InfluxDB?"
            )

        # Recorded but no longer a training target: the model predicts energy
        # per interval only.
        trainings_data[POWER_FIELD] = round(production_data[POWER_FIELD])
        trainings_data[ENERGY_FIELD] = round(production_data[ENERGY_FIELD], 2)
        return trainings_data

    async def write_new_training_data_to_influxdb(self, trainings_data):
        point = Point("forecast_training")
        for key, value in trainings_data.items():
            if isinstance(value, (int, float, str, bool)):
                point.field(key, value)

        point.time(trainings_data["time"].astimezone(timezone.utc))

        logger.info("Write new forecast training data to influxdb")
        logger.debug(trainings_data)
        await self.influxdb.write_point(point)

    async def train(self) -> None:
        data = await self.influxdb.query_dataframe("training_data")
        data["time"] = data["_time"].dt.tz_convert(LOCAL_TZ)
        await to_thread(self.training, data)

    def training(self, data: DataFrame) -> None:
        try:
            self.forecaster.train(OpenWeatherMapBaseData.to_canonical_frame(data))
        except PVLearnError as error:
            raise InvalidDataException(str(error)) from error

    @EventBus.subscribe(Interval10MinTriggerEvent)
    async def forecast_loop(self, event: Interval10MinTriggerEvent) -> None:
        predictions = await self.predict()
        await self._write_periods_to_influxdb(predictions)
        await self.publish_forecast()

    async def predict(self) -> DataFrame:
        if not self.forecaster.is_trained:
            await self.train()

        if self.last_weather_forecast is None:
            raise InvalidDataException(
                "Missing weather forecast for production forecast"
            )

        data = self._prepare_estimation_data(self.last_weather_forecast)

        try:
            return await self.forecaster.predict(data)
        except PVLearnError as error:
            raise InvalidDataException(str(error)) from error

    async def predict_elapsed_today(self) -> DataFrame:
        """Predict the hours of today that are already over.

        The weather forecast starts at the current hour, so the elapsed hours
        are reconstructed from the snapshots stored in `forecast_training`.
        Returns an empty frame when today has no stored hours yet.
        """
        if not self.forecaster.is_trained:
            await self.train()

        data = await self.influxdb.query_dataframe("training_data")
        if data.empty:
            return DataFrame()

        data["time"] = data["_time"].dt.tz_convert(LOCAL_TZ)

        hour_start = (
            datetime.now().astimezone().replace(minute=0, second=0, microsecond=0)
        )
        day_start = hour_start.replace(hour=0)

        elapsed = cast(
            DataFrame, data[(data["time"] >= day_start) & (data["time"] < hour_start)]
        )
        if elapsed.empty:
            logger.warning(
                "No stored weather between {day_start} and {hour_start}, "
                "the elapsed hours of today stay out of the forecast "
                "(latest stored hour: {latest})",
                day_start=day_start,
                hour_start=hour_start,
                latest=data["time"].max(),
            )
            return DataFrame()

        logger.info(
            "Reconstructing {count} elapsed hours of today from stored weather",
            count=len(elapsed),
        )

        try:
            return await self.forecaster.predict(
                OpenWeatherMapBaseData.to_canonical_frame(elapsed)
            )
        except PVLearnError as error:
            raise InvalidDataException(str(error)) from error

    @staticmethod
    def _prepare_estimation_data(
        weather_forecast_list: list[OpenWeatherMapForecastData],
    ) -> DataFrame:
        estimation_data_list = [
            {
                "time": datetime(
                    year=weather_forecast.year,
                    month=weather_forecast.month,
                    day=weather_forecast.day,
                    hour=weather_forecast.hour,
                    minute=0,
                    second=0,
                    microsecond=0,
                ).astimezone(),
                **weather_forecast.model_dump_canonical(),
            }
            for weather_forecast in weather_forecast_list
        ]

        data = DataFrame(estimation_data_list)
        data["time"] = to_datetime(data["time"], utc=True).dt.tz_convert(LOCAL_TZ)

        return data

    async def _write_periods_to_influxdb(self, periods: DataFrame) -> None:
        points = []
        for _, period in periods.iterrows():
            energy_wh = period[ENERGY_FIELD]
            period_time = period["time"]
            if not isinstance(period_time, datetime):
                raise InvalidDataException("Forecast period time must be datetime")
            if not isinstance(energy_wh, (int, float)):
                raise InvalidDataException("Forecast energy value must be numeric")

            point = Point("forecast")
            # pvlearn publishes Wh, this measurement stores kWh.
            point.field(ENERGY_FIELD, energy_wh / WH_PER_KWH)
            # Deprecated, mirrors the energy: at 60 minutes the mean power in W
            # equals the energy in Wh. Written as an integer, the type the
            # field has carried since the power model wrote it.
            point.field(POWER_FIELD, int(round(energy_wh)))

            point.time(period_time.astimezone(timezone.utc))
            points.append(point)

        logger.info("Write forecast data to influxdb")
        await self.influxdb.write_points(points)

    async def publish_forecast(self) -> None:
        forecast_data = await self.influxdb.query_dataframe("forecast")
        if not forecast_data.empty:
            forecast_data["time"] = forecast_data["_time"].dt.tz_convert(LOCAL_TZ)
            energy_hours: dict[datetime, int] = {}
            for _, row in forecast_data.iterrows():
                row_time = row["time"]
                row_energy = row[ENERGY_FIELD]

                if not isinstance(row_time, datetime):
                    raise InvalidDataException(
                        "Forecast row time must be datetime",
                    )
                if not isinstance(row_energy, (int, float)):
                    raise InvalidDataException(
                        "Forecast energy value must be numeric",
                    )

                energy_hours[row_time] = int(round(row_energy * WH_PER_KWH))

            forecast = Forecast.from_energy_period(
                energy_hours,
                timezone=str(LOCAL_TZ),
                battery_charge_needed_wh=self.battery_charge_needed_wh(),
            )
            logger.debug(forecast)

            await EventBus.emit(
                MQTTPublishEvent(
                    forecast.mqtt_topic(),
                    forecast,
                    self.settings.retain,
                )
            )
            await EventBus.emit(ForecastEvent(forecast))
