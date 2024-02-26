import time  # Importieren der time Bibliothek
from datetime import datetime, timedelta, timezone

import pandas as pd
from pandas import DataFrame, to_datetime
from pysolar.solar import get_altitude, get_azimuth
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler
from sklearn.feature_selection import SelectFromModel

from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import OpenWeatherMapForecastData
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.persistence.influxdb import InfluxDB, Point
from solaredge2mqtt.service.weather import WeatherClient
from solaredge2mqtt.settings import LocationSettings


class Forecast:

    def __init__(
        self,
        location: LocationSettings,
        mqtt: MQTTClient,
        influxdb: InfluxDB,
        weather: WeatherClient,
    ):
        self.location = location
        self.mqtt = mqtt
        self.influxdb = influxdb
        self.weather = weather

        self.forecaster = Forecaster("power")

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

        if rounded_minutes == 10 or not self.forecaster.is_trained:
            self.train()

    def get_weather_training(
        self, forecast_time: datetime
    ) -> dict[str, str | float | int | None]:
        if (
            self.last_weather_forecast is None
            or forecast_time.hour != self.last_weather_forecast[0].hour
        ):
            logger.info("Retrieve weather forecast for training of production forecast")
            self.last_weather_forecast = self.weather.get_weather(True).hourly

        if self.last_weather_forecast[0].hour != forecast_time.hour:
            raise InvalidDataException("Missing weather forecast for previous hour")

        return self.last_weather_forecast[0].model_dump_estimation_data()

    def add_last_10_minutes_pv_production(
        self, trainings_data
    ) -> dict[str, str | float | int | None]:
        production_data = self.influxdb.query_first("production")

        if production_data is None:
            raise InvalidDataException("Missing production data for last 10 minutes")

        trainings_data["power"] = round(production_data["power"])
        trainings_data["energy"] = round(production_data["energy"], 2)
        return trainings_data

    def write_new_training_data_to_influxdb(self, trainings_data):
        point = Point("forecast_training")
        for key, value in trainings_data.items():
            if isinstance(value, (int, float, str, bool)):
                point.field(key, value)

        point.time(trainings_data["time"].astimezone(timezone.utc))

        logger.info("Write new training data to influxdb")
        logger.debug(trainings_data)
        self.influxdb.write_point_to_aggregated_bucket(point)

    def train(self) -> None:
        data = self.influxdb.query_dataframe("training_data")
        self.forecaster.train(data)

    def replay_prediction(self, data):
        data = self.forecaster.predict(data)
        data["time"] = data["_time"]
        periods = self._calculate_periods_prediction(data)
        self._write_periods_to_influxdb(periods)
        pd.set_option("display.max_rows", None)
        logger.info(periods)

    async def forecast_loop(self):
        if not self.forecaster.is_trained:
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
        data = self.forecaster.predict(data)

        periods = self._calculate_periods_prediction(data)
        self._write_periods_to_influxdb(periods)

        hours = self._calculate_hourly_prediction(periods)
        logger.debug("Forecasted next hour: {hours}", hours=hours)
        await self._publish_hours_to_mqtt(hours)

    def _calculate_periods_prediction(self, data) -> DataFrame:
        data.loc[data["sun_altitude"] < -10, "power"] = 0

        data["energy"] = data["power"].apply(
            lambda x: round(x / 6000, 3) if x >= 0 else 0
        )
        data["power"] = data["power"].apply(lambda x: round(x) if x >= 0 else 0)

        return data[["time", "year", "month", "day", "hour", "energy", "power"]]

    def _calculate_hourly_prediction(self, data) -> DataFrame:
        hourly = data.groupby(["year", "month", "day", "hour"], as_index=False)[
            "energy"
        ].sum()

        hourly["power"] = data.groupby(
            ["year", "month", "day", "hour"], as_index=False
        )["power"].mean()["power"]

        hourly["time"] = hourly.apply(
            lambda row: to_datetime(
                f"{int(row['year'])}-{int(row['month'])}-{int(row['day'])}T{int(row['hour'])}:00:00"
            ).tz_localize(self.location.timezone),
            axis=1,
        )

        return hourly[["time", "year", "month", "day", "hour", "energy", "power"]]

    def _write_periods_to_influxdb(self, periods: DataFrame) -> None:
        points = []
        for _, period in periods.iterrows():
            point = Point("forecast")
            point.field("energy", period["energy"])
            point.field("power", period["power"])
            utc_time = period["time"].astimezone(timezone.utc)
            point.time(utc_time)
            points.append(point)

        logger.info("Write forecast data to influxdb")
        self.influxdb.write_points_to_aggregated_bucket(points)

    async def _publish_hours_to_mqtt(self, hours: DataFrame) -> None:
        data = hours[["time", "power", "energy"]]
        data = self._replace_time_with_iso(data)
        await self.mqtt.publish_to("forecast/hourly", data.to_json(orient="records"))

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
        "clear_sky_dhi",
        "clear_sky_dni",
        "clear_sky_ghi",
        "clouds",
        "cloudy_sky_dhi",
        "cloudy_sky_dni",
        "cloudy_sky_ghi",
        "dew_point",
        "feels_like",
        "humidity",
        "pop",
        "pressure",
        "rain",
        "sun_altitude",
        "sun_azimuth",
        "temp",
        "uvi",
        "visibility",
        "wind_deg",
        "wind_speed",
        "wind_gust",
    ]
    CATEGORICAL_FEATURES: list[str] = ["hour", "month", "weather_id", "weather_main"]

    def __init__(self, target_column: str) -> None:
        self.target_column: str = target_column
        self.model_pipeline: Pipeline = None

    def _prepare_data(self, data: DataFrame) -> DataFrame:
        all_features = self.NUMERIC_FEATURES + self.CATEGORICAL_FEATURES
        relevant_features = [col for col in all_features if col in data.columns]
        logger.debug(relevant_features)
        return data[relevant_features]

    def train(self, data: DataFrame) -> None:
        data_count = len(data)
        if data_count < 300:
            raise InvalidDataException("Not enough data to train the model")

        logger.info(
            f"Training model {self.target_column} with {data_count} data points"
        )

        start_time = time.time()

        x_vector = data.drop(columns=[self.target_column])
        y_vector = data[self.target_column]

        x_prepared = self._prepare_data(x_vector)

        numeric_cols = [
            col for col in self.NUMERIC_FEATURES if col in x_prepared.columns
        ]
        categorical_cols = [
            col for col in self.CATEGORICAL_FEATURES if col in x_prepared.columns
        ]

        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "num",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="median")),
                            ("scaler", RobustScaler()),
                        ]
                    ),
                    numeric_cols,
                ),
                (
                    "cat",
                    Pipeline(
                        [
                            ("imputer", SimpleImputer(strategy="most_frequent")),
                            ("encoder", OneHotEncoder(handle_unknown="ignore")),
                        ]
                    ),
                    categorical_cols,
                ),
            ]
        )

        self.model_pipeline = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                (
                    "feature_selector",
                    SelectFromModel(GradientBoostingRegressor(random_state=42)),
                ),
                ("model", GradientBoostingRegressor(random_state=42)),
            ]
        )

        x_train, x_test, y_train, y_test = train_test_split(
            x_prepared, y_vector, test_size=0.2, random_state=42
        )

        self.model_pipeline.fit(x_train, y_train)

        end_time = time.time()
        execution_time = end_time - start_time

        transformed_feature_names = self.model_pipeline[
            "preprocessor"
        ].get_feature_names_out()
        logger.debug(transformed_feature_names)

        selected_features_mask = self.model_pipeline["feature_selector"].get_support()
        logger.trace(selected_features_mask)
        selected_features = transformed_feature_names[selected_features_mask]

        predictions = self.model_pipeline.predict(x_test)
        mse = mean_squared_error(y_test, predictions)

        logger.info(f"Training MSE: {mse}")
        logger.info(f"Training execution time: {execution_time:.2f} seconds")
        logger.info(
            "Selected features ({count}): {features} ",
            count=len(selected_features),
            features=", ".join(selected_features),
        )

    @property
    def is_trained(self) -> bool:
        return self.model_pipeline is not None

    def predict(self, new_data: DataFrame) -> DataFrame:
        if self.model_pipeline is None:
            raise InvalidDataException("The model has not been trained yet.")

        data_for_prediction = new_data.copy()
        prepared_data_for_prediction = self._prepare_data(data_for_prediction)

        predictions = self.model_pipeline.predict(prepared_data_for_prediction)
        data_for_prediction[self.target_column] = predictions

        return data_for_prediction
