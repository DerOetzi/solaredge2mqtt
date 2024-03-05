from __future__ import annotations

import asyncio as aio
import time
from datetime import datetime, timedelta, timezone

from numpy import cos, percentile, pi, sin
from pandas import DataFrame, to_datetime
from pysolar.solar import get_altitude, get_azimuth
from sklearn import clone
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.model_selection import (GridSearchCV, TimeSeriesSplit,
                                     train_test_split)
from sklearn.pipeline import Pipeline

from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import EnumModel, OpenWeatherMapForecastData
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.service.influxdb import InfluxDB, Point
from solaredge2mqtt.service.weather import WeatherClient
from solaredge2mqtt.settings import ForecastSettings, LocationSettings


class ForecasterType(EnumModel):
    ENERGY = "energy"
    POWER = "power"

    def __init__(self, target_column: str) -> None:
        self._target_column: str = target_column

    @property
    def target_column(self) -> str:
        return self._target_column

    def prepare_value(self, value: float | int) -> float | int:
        if value <= 0:
            prepared = 0
        elif self.target_column == "energy":
            prepared = round(value / 1000, 3)
        else:
            prepared = int(round(value))

        return prepared


class Forecast:

    def __init__(
        self,
        settings: ForecastSettings,
        location: LocationSettings,
        mqtt: MQTTClient,
        influxdb: InfluxDB,
        weather: WeatherClient,
    ) -> None:
        self.settings = settings
        self.location = location
        self.mqtt = mqtt
        self.influxdb = influxdb
        self.weather = weather

        self.forecasters: dict[ForecasterType, Forecaster] = {
            typed: Forecaster(typed, settings.hyperparametertuning)
            for typed in ForecasterType
        }

        self.last_weather_forecast: list[OpenWeatherMapForecastData] | None = None

    async def training_loop(self):
        now = datetime.now().astimezone()
        rounded_minutes = (now.minute // 10) * 10
        last_10_minutes = now.replace(
            minute=rounded_minutes, second=0, microsecond=0
        ) - timedelta(minutes=10)

        training_data = self.get_weather_training(last_10_minutes)
        training_data = self.add_sun_position(last_10_minutes, training_data)
        training_data = self.add_last_10_minutes_pv_production(training_data)

        self.write_new_training_data_to_influxdb(training_data)

        if (
            rounded_minutes == 10
            or not self.forecasters[ForecasterType.ENERGY].is_trained
            or not self.forecasters[ForecasterType.POWER].is_trained
        ):
            await self.train()

    def get_weather_training(
        self, forecast_time: datetime
    ) -> dict[str, str | float | int | None]:
        if (
            self.last_weather_forecast is None
            or forecast_time.hour != self.last_weather_forecast[0].hour
        ):
            logger.info("Retrieve weather forecast for training of production forecast")
            self.last_weather_forecast = self.weather.get_weather().hourly

        if self.last_weather_forecast[0].hour != forecast_time.hour:
            raise InvalidDataException("Missing weather forecast for previous hour")

        return self.last_weather_forecast[0].model_dump_estimation_data()

    def add_last_10_minutes_pv_production(
        self, trainings_data
    ) -> dict[str, str | float | int | None]:
        production_data = self.influxdb.query_first("production")

        if production_data is None:
            raise InvalidDataException("Missing production data for last 10 minutes")

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

        logger.info("Write new training data to influxdb")
        logger.debug(trainings_data)
        self.influxdb.write_point(point)

    async def train(self) -> None:
        data = await self.influxdb.query_dataframe("training_data")
        data["time"] = data["_time"].dt.tz_convert(self.location.timezone)
        await aio.to_thread(self.training, data)

    def training(self, data: DataFrame) -> None:
        for forecaster in self.forecasters.values():
            forecaster.train(data)
            # self.replay_prediction(data, forecaster)

    def replay_prediction(self, data: DataFrame, forecaster: Forecaster) -> None:
        """FOR DEVELOPMENT PURPOSE ONLY"""
        logger.warning("Replaying prediction for development purpose")
        data = forecaster.predict(data)
        data["time"] = data["_time"]
        periods = self._calculate_periods_prediction(data, forecaster.typed)
        self._write_periods_to_influxdb(periods, forecaster.typed)

    async def forecast_loop(self):
        if (
            not self.forecasters[ForecasterType.ENERGY].is_trained
            or not self.forecasters[ForecasterType.POWER].is_trained
        ):
            raise InvalidDataException("Forecast model is not trained yet")

        if self.last_weather_forecast is None:
            raise InvalidDataException("Missing weather forecast for forecast")

        estimation_data_list = [
            dict(
                self.add_sun_position(
                    datetime(
                        year=weather_forecast.year,
                        month=weather_forecast.month,
                        day=weather_forecast.day,
                        hour=weather_forecast.hour,
                        minute=minute,
                        second=0,
                        microsecond=0,
                    ).astimezone(),
                    weather_forecast.model_dump_estimation_data(),
                )
            )
            for weather_forecast in self.last_weather_forecast
            for minute in range(0, 60, 10)
        ]

        data = DataFrame(estimation_data_list)
        data = self.add_last_10_minutes_pv_production(data)

        for typed, forecaster in self.forecasters.items():
            predicted_data = forecaster.predict(data)

            periods = self._calculate_periods_prediction(predicted_data, typed)
            self._write_periods_to_influxdb(periods, typed)

            hours = self._calculate_hourly_prediction(periods, typed)
            logger.debug("Forecasted next hour: {hours}", hours=hours)
            await self._publish_hours_to_mqtt(hours, typed)

    def _calculate_periods_prediction(
        self, data: DataFrame, typed: ForecasterType
    ) -> DataFrame:
        data["year"] = data["time"].dt.year
        data["month"] = data["time"].dt.month
        data["day"] = data["time"].dt.day
        data["hour"] = data["time"].dt.hour

        return data[["time", "year", "month", "day", "hour", typed.target_column]]

    def _calculate_hourly_prediction(
        self, data: DataFrame, typed: ForecasterType
    ) -> DataFrame:

        if typed == ForecasterType.ENERGY:
            hourly = data.groupby(["year", "month", "day", "hour"], as_index=False)[
                ForecasterType.ENERGY.target_column
            ].sum()
        elif typed == ForecasterType.POWER:
            hourly = data.groupby(["year", "month", "day", "hour"], as_index=False)[
                ForecasterType.POWER.target_column
            ].mean()

        hourly["time"] = hourly.apply(
            lambda row: to_datetime(
                f"{int(row['year'])}-{int(row['month'])}-{int(row['day'])}T{int(row['hour'])}:00:00"
            ).tz_localize(self.location.timezone),
            axis=1,
        )

        return hourly[["time", "year", "month", "day", "hour", typed.target_column]]

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

    async def _publish_hours_to_mqtt(
        self, hours: DataFrame, typed: ForecasterType
    ) -> None:
        data = hours[["time", typed.target_column]]
        data = self._replace_time_with_iso(data)
        await self.mqtt.publish_to(
            f"forecast/{typed.target_column}/hourly", data.to_json(orient="records")
        )

    @staticmethod
    def _replace_time_with_iso(data: DataFrame) -> str:
        data = data.copy()
        data["time"] = data["time"].dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        return data

    def add_sun_position(
        self, last_10_minutes, data
    ) -> dict[str, str | float | int | None]:
        data["time"] = last_10_minutes

        sun_time = last_10_minutes + timedelta(minutes=5)
        data["sun_azimuth"] = round(
            get_azimuth(self.location.latitude, self.location.longitude, sun_time), 2
        )
        data["sun_altitude"] = round(
            get_altitude(self.location.latitude, self.location.longitude, sun_time), 2
        )

        return data


class Forecaster:
    NUMERIC_FEATURES: list[str] = [
        "clouds",
        "dew_point",
        "feels_like",
        "humidity",
        "pop",
        "pressure",
        "rain",
        "sun_altitude",
        "temp",
        "uvi",
        "visibility",
        "wind_speed",
        "wind_gust",
    ]
    CATEGORICAL_FEATURES: list[str] = ["weather_id", "weather_main"]
    CYCLICAL_FEATURES: dict[str, int] = {
        "wind_deg": 360,
        "sun_azimuth": 360,
    }
    TIME_FEATURES: list[str] = ["time"]
    TARGET_FEATURES: dict[str, str] = {
        ForecasterType.ENERGY.target_column: "energy",
        ForecasterType.POWER.target_column: "power",
    }

    def __init__(
        self, typed: ForecasterType, enable_hyperparameter_tuning: bool = False
    ) -> None:
        self.typed: ForecasterType = typed
        self.enable_hyperparameter_tuning = enable_hyperparameter_tuning
        self.model_pipeline: Pipeline = None

    def train(self, data: DataFrame) -> None:
        data_count = len(data)
        if data_count < 300:
            raise InvalidDataException("Not enough data to train the model")

        logger.info(f"Training model {self.typed} with {data_count} data points")

        start_time = time.time()
        y_vector = data[self.typed.target_column]

        pipeline = self._prepare_model_pipeline(data.columns.to_list())

        if self.enable_hyperparameter_tuning:
            self.model_pipeline = self._hyperparametertuning(data, y_vector, pipeline)
        else:
            self.model_pipeline = pipeline

        self.model_pipeline.fit(data, y_vector)

        execution_time = time.time() - start_time

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
                    self._extract_used_columns(self.TIME_FEATURES, x_vector_columns),
                ),
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

    def predict(self, new_data: DataFrame) -> DataFrame:
        if self.model_pipeline is None:
            raise InvalidDataException("The model has not been trained yet.")

        data_for_prediction = new_data.copy()

        predictions = self.model_pipeline.predict(data_for_prediction)
        data_for_prediction[self.typed.target_column] = predictions
        data_for_prediction.loc[
            data_for_prediction["sun_altitude"] < -10, self.typed.target_column
        ] = 0
        data_for_prediction[self.typed.target_column] = data_for_prediction[
            self.typed.target_column
        ].apply(self.typed.prepare_value)

        return data_for_prediction


class BaseEncoder(BaseEstimator, TransformerMixin):
    def __init__(self) -> None:
        self.features: list[str] | None = None
        self._feature_names_out: list[str] = []

    def fit(self, x_vector: DataFrame, *_) -> BaseEncoder:
        if not hasattr(x_vector, "columns"):
            raise AttributeError("x_vector has no columns")

        self.features = x_vector.columns.tolist()
        return self

    def _transform(self, x_vector: DataFrame) -> DataFrame:
        if self.features is None:
            raise AttributeError(f"Encoder {self.__class__} is not been fitted yet.")

        if not hasattr(x_vector, "columns"):
            raise AttributeError("x_vector has no columns")

        if not all(feature in self.features for feature in x_vector.columns):
            raise AttributeError(f"Columns {x_vector.columns} are not in the vector")

        if not all(feature in x_vector.columns for feature in self.features):
            raise AttributeError(f"Columns {self.features} are not in the vector")

        return x_vector

    def _save_feature_names_out(self, x_vector: DataFrame) -> DataFrame:
        self._feature_names_out = x_vector.columns.to_list()
        return x_vector

    def get_feature_names_out(self, *_) -> list[str]:
        return self._feature_names_out


class CyclicalEncoder(BaseEncoder):
    def __init__(self, **cycle_lengths: dict[str, int]) -> None:
        super().__init__()
        self.cycle_lengths: dict[str, int] = cycle_lengths

    def transform(self, x_vector: DataFrame) -> DataFrame:
        x_vector = self._transform(x_vector)
        for feature in self.features:
            cycle = self.cycle_lengths.get(feature, None)
            if not cycle:
                raise ValueError(f"Unknown cyclical feature {feature}")

            x_vector = self.transform_cycle_columns(
                x_vector, feature, x_vector[feature], cycle
            )
            x_vector.drop(feature, axis=1, inplace=True)

        return self._save_feature_names_out(x_vector)

    def get_params(self, deep=True) -> dict[str, int]:
        return self.cycle_lengths

    @staticmethod
    def transform_cycle_columns(
        x_vector: DataFrame, prefix: str, cycle_vector: DataFrame, cycle_length: int
    ) -> DataFrame:
        x_vector[f"{prefix}_cos"] = cos(2 * pi * cycle_vector / cycle_length)
        x_vector[f"{prefix}_sin"] = sin(2 * pi * cycle_vector / cycle_length)

        return x_vector


class TimeEncoder(BaseEncoder):
    def transform(self, x_vector: DataFrame) -> DataFrame:
        x_vector = self._transform(x_vector)
        for feature in self.features:

            x_vector = CyclicalEncoder.transform_cycle_columns(
                x_vector, f"{feature}_hour", x_vector[feature].dt.hour, 24
            )

            x_vector = CyclicalEncoder.transform_cycle_columns(
                x_vector, f"{feature}_month", x_vector[feature].dt.month, 12
            )

            x_vector[f"{feature}_dst"] = (
                x_vector[feature]
                .apply(lambda x: x.dst() != timedelta(0))
                .astype("category")
            )

            logger.debug(x_vector.head())
            x_vector.drop(feature, axis=1, inplace=True)

        return self._save_feature_names_out(x_vector)


class CategoricalEncoder(BaseEncoder):
    def transform(self, x_vector) -> DataFrame:
        x_vector = self._transform(x_vector).astype("category")
        return self._save_feature_names_out(x_vector)


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
