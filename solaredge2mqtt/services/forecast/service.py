from __future__ import annotations

from asyncio import to_thread
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from pandas import DataFrame, to_datetime
from pvlearn.config import ForecasterConfig
from pvlearn.exceptions import ModelNotTrainedError, PVLearnError, SchemaMismatchError
from pvlearn.forecaster import Forecaster
from pvlearn.location import Location
from pvlearn.schema import (
    CATEGORICAL_FEATURES,
    CYCLICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_FEATURE,
    TIME_FEATURE,
)
from tzlocal import get_localzone

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.storage import Point, StorageService
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.forecast.models import Forecast
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.result import WeatherSnapshot

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import LocationSettings


LOCAL_TZ = get_localzone()

#: Resolution of the weather forecast, the training data and the prediction.
INTERVAL_MINUTES = 60

ENERGY_FIELD = "energy"
POWER_FIELD = "power"

WH_PER_KWH = 1000

TRAINING_MEASUREMENT = "forecast_training"

FORECAST_MEASUREMENT = "forecast"

TRAINING_START = datetime(2024, 1, 1, tzinfo=timezone.utc)

HOURS_PER_DAY = 24

THROTTLE_TRAINING_DAYS = 30
THROTTLE_TRAINING_ROWS = THROTTLE_TRAINING_DAYS * HOURS_PER_DAY * 60 // INTERVAL_MINUTES

FREQUENT_TRAINING_INTERVAL_HOURS = 1
THROTTLED_TRAINING_INTERVAL_HOURS = 24

DUE_TOLERANCE = timedelta(minutes=5)

FORECAST_DAYS = 2

MODEL_DIRECTORY = "model"


#: The columns pvlearn trains and predicts on, in the order of its schema.
PVLEARN_COLUMNS: tuple[str, ...] = (
    TIME_FEATURE,
    TARGET_FEATURE,
    *NUMERIC_FEATURES,
    *CATEGORICAL_FEATURES,
    *CYCLICAL_FEATURES,
)


def frame_from_records(records: list[dict[str, Any]]) -> DataFrame:
    if not records:
        return DataFrame()

    data = DataFrame(records)
    data["_time"] = to_datetime(data["_time"], utc=True)
    data["time"] = data["_time"].dt.tz_convert(LOCAL_TZ)

    return data


def frame_for_pvlearn(data: DataFrame) -> DataFrame:
    """Reduce a stored frame to the canonical columns pvlearn knows.

    The storage holds the canonical schema, so nothing is renamed here. Columns
    outside the schema are dropped, columns a row predates are left missing;
    the forecaster tolerates both.
    """
    return cast(
        "DataFrame", data[[column for column in PVLEARN_COLUMNS if column in data]]
    )


class ForecastService:
    def __init__(
        self,
        settings: ForecastSettings,
        location: LocationSettings,
        storage: StorageService,
    ) -> None:
        self.settings = settings
        self.location = location

        self.storage = storage

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
        self.forecaster_location = forecaster_location
        self.forecaster_config = forecaster_config

        self.last_weather_forecast: list[WeatherSnapshot] | None = None
        self.last_hour_forecast: dict[int, WeatherSnapshot] | None = None

        self.last_battery_capacity_wh: float | None = None
        self.last_battery_stored_energy_wh: float | None = None

        self.last_training: datetime | None = None

        self.forecaster = self._restore_forecaster()

        EventBus.register(self)

    @property
    def model_directory(self) -> Path | None:
        if self.settings.cachingdir is None:
            return None

        return Path(self.settings.cachingdir) / MODEL_DIRECTORY

    def _restore_forecaster(self) -> Forecaster:
        directory = self.model_directory

        if directory is not None:
            try:
                forecaster = Forecaster.load(
                    directory, self.forecaster_location, self.forecaster_config
                )
            except ModelNotTrainedError:
                logger.info(
                    "No forecast model persisted in {directory}, training from scratch",
                    directory=directory,
                )
            except SchemaMismatchError as error:
                logger.warning(
                    "Persisted forecast model cannot be used, "
                    "training from scratch: {error}",
                    error=error,
                )
            else:
                if forecaster.metadata is not None:
                    self.last_training = forecaster.metadata.trained_at

                return forecaster

        return Forecaster(self.forecaster_location, self.forecaster_config)

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
        self, last_hour_weather_forecast: WeatherSnapshot
    ) -> None:
        now = datetime.now().astimezone()
        last_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

        training_data = last_hour_weather_forecast.model_dump_canonical()
        training_data["time"] = last_hour
        training_data = await self.add_last_hour_pv_production(training_data)
        await self.store_training_data(training_data)

        if (now.minute // 10) * 10 == 20:
            await self.scheduled_training()

    async def add_last_hour_pv_production(
        self, trainings_data
    ) -> dict[str, str | float | int | None]:
        production_data = await self.storage.query_production_last_hour()

        if production_data is None:
            raise InvalidDataException(
                "Missing production data of last hour for forecast training."
                + " Did the service write power information to the storage?"
            )

        # Recorded but no longer a training target: the model predicts energy
        # per interval only.
        trainings_data[POWER_FIELD] = round(production_data[POWER_FIELD])
        trainings_data[ENERGY_FIELD] = round(production_data[ENERGY_FIELD], 2)
        return trainings_data

    async def store_training_data(self, trainings_data):
        point = Point(TRAINING_MEASUREMENT)
        for key, value in trainings_data.items():
            if isinstance(value, (int, float, str, bool)):
                point.field(key, value)

        point.time(trainings_data["time"].astimezone(timezone.utc))

        logger.info("Write new forecast training data to storage")
        logger.debug(trainings_data)
        await self.storage.write_point(point)

    async def read_training_data(self) -> DataFrame:
        rows = await self.storage.query_pivot(
            TRAINING_MEASUREMENT, int(TRAINING_START.timestamp())
        )

        return frame_from_records(rows)

    async def scheduled_training(self) -> None:
        data = await self.read_training_data()
        if data.empty:
            raise InvalidDataException("No forecast training data available")

        interval_hours = self.training_interval_hours(len(data))

        if not self._is_due(self.last_training, timedelta(hours=interval_hours)):
            logger.info(
                "Skipping forecast training, last trained at {last}, "
                "retraining every {hours} hours",
                last=self.last_training,
                hours=interval_hours,
            )
            return

        await self.train(data)

    def training_interval_hours(self, rows: int) -> int:
        if self.settings.training_interval_hours > 0:
            return self.settings.training_interval_hours

        if rows >= THROTTLE_TRAINING_ROWS:
            return THROTTLED_TRAINING_INTERVAL_HOURS

        return FREQUENT_TRAINING_INTERVAL_HOURS

    def hyperparametertuning_due(self) -> bool:
        if not self.settings.hyperparametertuning:
            return False

        interval_days = self.settings.hyperparametertuning_interval_days
        if interval_days <= 0:
            return True

        return self._is_due(
            self.forecaster.hyperparameters_tuned_at, timedelta(days=interval_days)
        )

    @staticmethod
    def _is_due(last_run: datetime | None, interval: timedelta) -> bool:
        if last_run is None:
            return True

        return datetime.now().astimezone() - last_run >= interval - DUE_TOLERANCE

    async def train(self, data: DataFrame | None = None) -> None:
        if data is None:
            data = await self.read_training_data()

        if data.empty:
            raise InvalidDataException("No forecast training data available")

        await to_thread(self.training, data, self.hyperparametertuning_due())

        self.last_training = datetime.now().astimezone()

    def training(self, data: DataFrame, hyperparametertuning: bool = False) -> None:
        try:
            self.forecaster.train(
                frame_for_pvlearn(data), hyperparametertuning=hyperparametertuning
            )
        except PVLearnError as error:
            raise InvalidDataException(str(error)) from error

        self.save_model()

    def save_model(self) -> None:
        directory = self.model_directory
        if directory is None:
            return

        try:
            self.forecaster.save(directory)
        except (PVLearnError, OSError) as error:
            logger.warning("Could not persist the forecast model: {error}", error=error)

    @EventBus.subscribe(Interval10MinTriggerEvent)
    async def forecast_loop(self, event: Interval10MinTriggerEvent) -> None:
        predictions = await self.predict()
        await self._write_periods(predictions)
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

        data = await self.read_training_data()
        if data.empty:
            return DataFrame()

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
            return await self.forecaster.predict(frame_for_pvlearn(elapsed))
        except PVLearnError as error:
            raise InvalidDataException(str(error)) from error

    @staticmethod
    def _prepare_estimation_data(
        weather_forecast_list: list[WeatherSnapshot],
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

    async def _write_periods(self, periods: DataFrame) -> None:
        points = []
        for _, period in periods.iterrows():
            energy_wh = period[ENERGY_FIELD]
            period_time = period["time"]
            if not isinstance(period_time, datetime):
                raise InvalidDataException("Forecast period time must be datetime")
            if not isinstance(energy_wh, (int, float)):
                raise InvalidDataException("Forecast energy value must be numeric")

            point = Point(FORECAST_MEASUREMENT)
            # pvlearn publishes Wh, this measurement stores kWh.
            point.field(ENERGY_FIELD, energy_wh / WH_PER_KWH)
            # Deprecated, mirrors the energy: at 60 minutes the mean power in W
            # equals the energy in Wh. Written as an integer, the type the
            # field has carried since the power model wrote it.
            point.field(POWER_FIELD, int(round(energy_wh)))

            point.time(period_time.astimezone(timezone.utc))
            points.append(point)

        logger.info("Write forecast data to storage")
        await self.storage.write_points(points)

    async def publish_forecast(self) -> None:
        rows = await self.storage.query_days(FORECAST_MEASUREMENT, FORECAST_DAYS)
        forecast_data = frame_from_records(rows)
        if not forecast_data.empty:
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
