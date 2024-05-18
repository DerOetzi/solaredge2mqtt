from __future__ import annotations

import time
from asyncio import Event, to_thread
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from numpy import percentile
from pandas import DataFrame
from sklearn import clone
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit, train_test_split
from sklearn.pipeline import Pipeline
from tzlocal import get_localzone_name

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDB, Point
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent
from solaredge2mqtt.services.forecast.encoders import (
    CategoricalEncoder,
    CyclicalEncoder,
    SunEncoder,
    TimeEncoder,
)
from solaredge2mqtt.services.forecast.events import ForecastEvent
from solaredge2mqtt.services.forecast.models import Forecast, ForecasterType
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.models import OpenWeatherMapForecastData

if TYPE_CHECKING:
    from solaredge2mqtt.core.settings.models import LocationSettings


LOCAL_TZ = get_localzone_name()


class ForecastService:
    def __init__(
        self,
        settings: ForecastSettings,
        location: LocationSettings,
        event_bus: EventBus,
        influxdb: InfluxDB,
    ) -> None:
        self.settings = settings
        self.location = location
        self.event_bus = event_bus
        self._subscribe_events()

        self.influxdb = influxdb

        self.forecasters: dict[ForecasterType, Forecaster] = {
            typed: Forecaster(typed, location, settings.hyperparametertuning)
            for typed in ForecasterType
        }

        self.last_weather_forecast: list[OpenWeatherMapForecastData] | None = None
        self.last_hour_forecast: dict[int, OpenWeatherMapForecastData] | None = None

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(WeatherUpdateEvent, self.weather_update)
        self.event_bus.subscribe(Interval10MinTriggerEvent, self.forecast_loop)

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
        training_data = self.add_last_hour_pv_production(training_data)
        self.write_new_training_data_to_influxdb(training_data)

        if (now.minute // 10) * 10 == 20:
            await self.train()

    def add_last_hour_pv_production(
        self, trainings_data
    ) -> dict[str, str | float | int | None]:
        production_data = self.influxdb.query_first("production")

        if production_data is None:
            raise InvalidDataException(
                "Missing production data of last hour for forecast training."
                + " Did the service write power information to InfluxDB?"
            )

        trainings_data[ForecasterType.POWER.target_column] = round(
            production_data[ForecasterType.POWER.target_column]
        )
        trainings_data[ForecasterType.ENERGY.target_column] = round(
            production_data[ForecasterType.ENERGY.target_column], 2
        )
        return trainings_data

    def write_new_training_data_to_influxdb(self, trainings_data):
        point = Point("forecast_training")
        for key, value in trainings_data.items():
            if isinstance(value, (int, float, str, bool)):
                point.field(key, value)

        point.time(trainings_data["time"].astimezone(timezone.utc))

        logger.info("Write new forecast training data to influxdb")
        logger.debug(trainings_data)
        self.influxdb.write_point(point)

    async def train(self) -> None:
        data = await self.influxdb.query_dataframe("training_data")
        data["time"] = data["_time"].dt.tz_convert(LOCAL_TZ)
        await to_thread(self.training, data)

    def training(self, data: DataFrame) -> None:
        for forecaster in self.forecasters.values():
            forecaster.train(data)

    async def forecast_loop(self, _):
        if (
            not self.forecasters[ForecasterType.ENERGY].is_trained
            or not self.forecasters[ForecasterType.POWER].is_trained
        ):
            await self.train()

        if self.last_weather_forecast is None:
            raise InvalidDataException(
                "Missing weather forecast for production forecast"
            )

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
                **weather_forecast.model_dump_estimation_data(),
            }
            for weather_forecast in self.last_weather_forecast
        ]

        data = DataFrame(estimation_data_list)
        data["time"] = data["time"].astype(f"datetime64[ns, {LOCAL_TZ}]")

        for typed, forecaster in self.forecasters.items():
            predicted_data = await forecaster.predict(data)
            self._write_periods_to_influxdb(predicted_data, typed)

        await self.publish_forecast()

    def _write_periods_to_influxdb(
        self, periods: DataFrame, typed: ForecasterType
    ) -> None:
        points = []
        for _, period in periods.iterrows():
            point = Point("forecast")
            point.field(typed.target_column, period[typed.target_column])
            utc_time = period["time"].astimezone(timezone.utc)
            point.time(utc_time)
            points.append(point)

        logger.info("Write forecast data to influxdb")
        self.influxdb.write_points(points)

    async def publish_forecast(self) -> None:
        forecast_data = await self.influxdb.query_dataframe("forecast")
        if not forecast_data.empty:
            forecast_data["time"] = forecast_data["_time"].dt.tz_convert(LOCAL_TZ)
            power_hours = {
                row["time"]: row["power"] for idx, row in forecast_data.iterrows()
            }
            energy_hours = {
                row["time"]: round(row["energy"] * 1000)
                for idx, row in forecast_data.iterrows()
            }
            forecast = Forecast(power_period=power_hours, energy_period=energy_hours)
            logger.debug(forecast)

            await self.event_bus.emit(MQTTPublishEvent(forecast.mqtt_topic(), forecast))
            await self.event_bus.emit(ForecastEvent(forecast))


class Forecaster:
    NUMERIC_FEATURES: list[str] = [
        "clouds",
        "dew_point",
        "feels_like",
        "humidity",
        "pop",
        "pressure",
        "rain",
        "temp",
        "uvi",
        "visibility",
        "wind_speed",
        "wind_gust",
    ]
    CATEGORICAL_FEATURES: list[str] = ["weather_id", "weather_main"]
    CYCLICAL_FEATURES: dict[str, int] = {
        "wind_deg": 360,
    }
    TARGET_FEATURES: dict[str, str] = {
        ForecasterType.ENERGY.target_column: "energy",
        ForecasterType.POWER.target_column: "power",
    }

    def __init__(
        self,
        typed: ForecasterType,
        location: LocationSettings,
        enable_hyperparameter_tuning: bool = False,
    ) -> None:
        self.typed: ForecasterType = typed
        self.location = location
        self.enable_hyperparameter_tuning = enable_hyperparameter_tuning
        self.model_pipeline: Pipeline = None
        self.training_completed: Event = Event()

    def train(self, data: DataFrame) -> None:
        data_count = len(data)
        logger.info(
            f"Training model {self.typed} with {data_count} hours of data points"
        )

        if data_count < 60:
            raise InvalidDataException(
                "Forecast needs at least 60 hours of data at least to start training",
            )

        self.training_completed.clear()
        start_time = time.time()
        y_vector = data[self.typed.target_column]

        pipeline = self._prepare_model_pipeline(data.columns.to_list())

        if self.enable_hyperparameter_tuning:
            self.model_pipeline = self._hyperparametertuning(data, y_vector, pipeline)
        else:
            self.model_pipeline = pipeline

        self.model_pipeline.fit(data, y_vector)

        execution_time = time.time() - start_time
        self.training_completed.set()

        transformed_features = self.model_pipeline[
            "preprocessor"
        ].get_feature_names_out()
        logger.debug(
            "Transformed features ({count}): {features} ",
            count=len(transformed_features),
            features=", ".join(transformed_features),
        )

        selected_features = self.model_pipeline[
            "feature_selector"
        ].important_features_.tolist()
        logger.info(
            "Selected features ({count}): {features} ",
            count=len(selected_features),
            features=", ".join(selected_features),
        )

        logger.info(f"Training execution time: {execution_time:.2f} seconds")

    def _hyperparametertuning(self, data, y_vector, pipeline):
        param_grid = {
            "model__max_iter": [100, 200, 300],
            "model__max_depth": [None, 5, 10],
            "model__learning_rate": [0.01, 0.1],
        }

        grid_search = GridSearchCV(
            estimator=pipeline,
            param_grid=param_grid,
            cv=TimeSeriesSplit(n_splits=2),
            scoring="neg_mean_squared_error",
        )
        grid_search.fit(data, y_vector)

        logger.info(
            "Training with best parameters: {params}", params=grid_search.best_params_
        )
        logger.info("Training with best score: {score}", score=grid_search.best_score_)

        return clone(grid_search.best_estimator_)

    def _prepare_model_pipeline(self, x_vector_columns: list[str]) -> None:
        return Pipeline(
            steps=[
                ("preprocessor", self._prepare_preprocessor(x_vector_columns)),
                (
                    "feature_selector",
                    PFISelector(
                        estimator=HistGradientBoostingRegressor(
                            random_state=42, categorical_features="from_dtype"
                        )
                    ),
                ),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        random_state=42, categorical_features="from_dtype"
                    ),
                ),
            ]
        )

    def _prepare_preprocessor(self, x_vector_columns: list[str]) -> ColumnTransformer:
        ct = ColumnTransformer(
            transformers=[
                (
                    "cyc",
                    CyclicalEncoder(**self.CYCLICAL_FEATURES),
                    self._extract_used_columns(
                        self.CYCLICAL_FEATURES, x_vector_columns
                    ),
                ),
                (
                    "num",
                    "passthrough",
                    self._extract_used_columns(self.NUMERIC_FEATURES, x_vector_columns),
                ),
                (
                    "time",
                    TimeEncoder(),
                    ["time"],
                ),
                ("sun", SunEncoder(self.location), ["time"]),
                (
                    "cat",
                    CategoricalEncoder(),
                    self._extract_used_columns(
                        self.CATEGORICAL_FEATURES, x_vector_columns
                    ),
                ),
            ],
            remainder="drop",
        )
        ct.set_output(transform="pandas")
        return ct

    @staticmethod
    def _extract_used_columns(
        typed_features: list[str] | dict[str, int], x_vector_columns: list[str]
    ) -> list[str]:
        return [col for col in typed_features if col in x_vector_columns]

    @property
    def is_trained(self) -> bool:
        return self.model_pipeline is not None

    async def predict(self, new_data: DataFrame) -> DataFrame:
        if self.model_pipeline is None:
            raise InvalidDataException("The model has not been trained yet.")

        data_for_prediction = new_data.copy()

        await self.training_completed.wait()

        predictions = self.model_pipeline.predict(data_for_prediction)
        data_for_prediction[self.typed.target_column] = predictions
        data_for_prediction[self.typed.target_column] = data_for_prediction[
            self.typed.target_column
        ].apply(self.typed.prepare_value)

        return data_for_prediction


class PFISelector(BaseEstimator, TransformerMixin):
    def __init__(self, estimator, n_repeats=10):
        self.estimator = estimator
        self.n_repeats = n_repeats

        self.estimator_ = None
        self.feature_importances_ = None
        self.important_indices_ = None
        self.important_features_ = None

    def fit(self, x_vector: DataFrame, y_vector=None) -> PFISelector:
        x_train, x_test, y_train, y_test = train_test_split(
            x_vector, y_vector, test_size=0.1, random_state=42
        )
        self.estimator_ = self.estimator.fit(x_train, y_train)
        results = permutation_importance(
            self.estimator_,
            x_test,
            y_test,
            n_repeats=self.n_repeats,
            random_state=42,
            n_jobs=-1,
        )

        self.feature_importances_ = results.importances_mean

        threshold_value = percentile(self.feature_importances_, 75)

        self.important_indices_ = self.feature_importances_ > threshold_value
        self.important_features_ = x_vector.columns[self.important_indices_]
        return self

    def transform(self, x_vector: DataFrame) -> DataFrame:
        return x_vector[self.important_features_]

    def get_support(self, *_) -> list[bool]:
        return self.important_indices_.to_list()
