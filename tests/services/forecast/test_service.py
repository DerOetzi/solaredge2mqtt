"""Tests for ForecastService with mocked ML dependencies."""

from datetime import datetime as dt_class
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest
from pandas import DataFrame
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.forecast.models import ForecasterType
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.forecast.service import (
    ForecastService,
    Forecaster,
    LOCAL_TZ,
    PFISelector,
)


class MockLocationSettings:
    """Mock LocationSettings for testing."""

    def __init__(self, latitude=52.52, longitude=13.405):
        self.latitude = latitude
        self.longitude = longitude


class MockOpenWeatherMapForecastData:
    """Mock OpenWeatherMapForecastData for testing."""

    def __init__(self, hour=12, year=2024, month=6, day=15):
        self.hour = hour
        self.year = year
        self.month = month
        self.day = day

    def model_dump_estimation_data(self):
        return {
            "temp": 25.0,
            "humidity": 50,
            "clouds": 20,
            "pressure": 1013,
            "wind_speed": 5.0,
            "wind_deg": 180,
            "uvi": 5.0,
            "pop": 0.1,
            "weather_id": 800,
            "weather_main": "Clear",
        }


class MockWeatherData:
    """Mock weather data wrapper."""

    def __init__(self, hourly=None):
        if hourly is None:
            hourly = [MockOpenWeatherMapForecastData(hour=i) for i in range(48)]
        self.hourly = hourly


class TestForecastServiceInit:
    """Tests for ForecastService initialization."""

    def test_forecast_service_init(self):
        """Test ForecastService initialization."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        assert service.settings == settings
        assert service.location == location
        assert service.event_bus == event_bus
        assert service.influxdb == influxdb
        assert service.last_weather_forecast is None
        assert service.last_hour_forecast is None

    def test_forecast_service_creates_forecasters(self):
        """Test ForecastService creates forecasters for each type."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        assert ForecasterType.ENERGY in service.forecasters
        assert ForecasterType.POWER in service.forecasters
        assert isinstance(service.forecasters[ForecasterType.ENERGY], Forecaster)
        assert isinstance(service.forecasters[ForecasterType.POWER], Forecaster)

    def test_forecast_service_subscribes_events(self):
        """Test ForecastService subscribes to events."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        # Check that subscribe was called for both event types
        assert event_bus.subscribe.call_count == 2


class TestForecastServiceWeatherUpdate:
    """Tests for ForecastService weather_update method."""

    @pytest.mark.asyncio
    async def test_weather_update_stores_forecast(self):
        """Test weather_update stores the weather forecast."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        weather_data = MockWeatherData()
        event = MagicMock()
        event.weather = weather_data

        await service.weather_update(event)

        assert service.last_weather_forecast == weather_data.hourly

    @pytest.mark.asyncio
    async def test_weather_update_initializes_last_hour_forecast(self):
        """Test weather_update initializes last_hour_forecast dict."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        weather_data = MockWeatherData()
        event = MagicMock()
        event.weather = weather_data

        await service.weather_update(event)

        assert service.last_hour_forecast is not None
        assert isinstance(service.last_hour_forecast, dict)

    @pytest.mark.asyncio
    async def test_weather_update_stores_current_hour(self):
        """Test weather_update stores current hour's forecast."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        # Use current hour to ensure it's not removed
        current_hour = dt_class.now().hour
        hourly_data = [MockOpenWeatherMapForecastData(hour=current_hour)]
        weather_data = MockWeatherData(hourly=hourly_data)
        event = MagicMock()
        event.weather = weather_data

        await service.weather_update(event)

        assert current_hour in service.last_hour_forecast
        assert service.last_hour_forecast[current_hour] == hourly_data[0]

    @pytest.mark.asyncio
    async def test_weather_update_cleans_old_hours(self):
        """Test weather_update removes old hour forecasts."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = MagicMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        # Pre-populate with old hours
        service.last_hour_forecast = {
            0: MagicMock(),
            5: MagicMock(),
            10: MagicMock(),
        }

        # Update with current hour 12
        hourly_data = [MockOpenWeatherMapForecastData(hour=12)]
        weather_data = MockWeatherData(hourly=hourly_data)
        event = MagicMock()
        event.weather = weather_data

        with patch("solaredge2mqtt.services.forecast.service.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 12
            mock_dt.now.return_value = mock_now
            mock_now.astimezone.return_value = mock_now
            mock_now.__sub__ = lambda self, x: MagicMock(hour=11)

            await service.weather_update(event)

        # Old hours (0, 5, 10) should be removed, only 12 and 11 kept
        assert 0 not in service.last_hour_forecast
        assert 5 not in service.last_hour_forecast
        assert 10 not in service.last_hour_forecast


class TestForecastServiceWriteTrainingData:
    """Tests for ForecastService write_new_training_data method."""

    @pytest.mark.asyncio
    async def test_write_new_training_data_calls_influxdb(self):
        """Test write_new_training_data writes to InfluxDB."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(return_value={
            "power": 1000.0,
            "energy": 5.0,
        })
        influxdb.write_point = AsyncMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        weather_forecast = MockOpenWeatherMapForecastData(hour=11)

        with patch(
            "solaredge2mqtt.services.forecast.service.datetime"
        ) as mock_datetime:
            mock_now = datetime(2024, 6, 15, 12, 30, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            await service.write_new_training_data(weather_forecast)

        influxdb.query_first.assert_called_once_with("production")
        influxdb.write_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_new_training_data_raises_on_missing_production(self):
        """Test write_new_training_data raises when production data missing."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(return_value=None)

        service = ForecastService(settings, location, event_bus, influxdb)

        weather_forecast = MockOpenWeatherMapForecastData(hour=11)

        with pytest.raises(InvalidDataException) as exc_info:
            await service.write_new_training_data(weather_forecast)

        assert "Missing production data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_write_new_training_data_triggers_train_at_20min(self):
        """Test write_new_training_data triggers training at minute 20."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(return_value={
            "power": 1000.0,
            "energy": 5.0,
        })
        influxdb.write_point = AsyncMock()
        influxdb.query_dataframe = AsyncMock(return_value=DataFrame())

        service = ForecastService(settings, location, event_bus, influxdb)
        service.train = AsyncMock()

        weather_forecast = MockOpenWeatherMapForecastData(hour=11)

        with patch(
            "solaredge2mqtt.services.forecast.service.datetime"
        ) as mock_datetime:
            # Minute 25 -> (25 // 10) * 10 = 20
            mock_now = datetime(2024, 6, 15, 12, 25, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now

            await service.write_new_training_data(weather_forecast)

        service.train.assert_called_once()


class TestForecastServiceForecastLoop:
    """Tests for ForecastService forecast_loop method."""

    @pytest.mark.asyncio
    async def test_forecast_loop_raises_without_weather(self):
        """Test forecast_loop raises when no weather forecast available."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        # Mock forecasters as trained
        for forecaster in service.forecasters.values():
            forecaster.model_pipeline = MagicMock()

        with pytest.raises(InvalidDataException) as exc_info:
            await service.forecast_loop(None)

        assert "Missing weather forecast" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_forecast_loop_triggers_training_if_not_trained(self):
        """Test forecast_loop triggers training when models not trained."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.query_dataframe = AsyncMock(return_value=DataFrame())

        service = ForecastService(settings, location, event_bus, influxdb)
        service.train = AsyncMock()

        # Forecasters not trained (model_pipeline is None)
        service.last_weather_forecast = [MockOpenWeatherMapForecastData()]

        with pytest.raises(InvalidDataException):
            await service.forecast_loop(None)

        service.train.assert_called_once()


class TestForecastServicePublishForecast:
    """Tests for ForecastService publish_forecast method."""

    @pytest.mark.asyncio
    async def test_publish_forecast_empty_data(self):
        """Test publish_forecast does nothing with empty data."""
        settings = ForecastSettings(enable=True, retain=True)
        location = MockLocationSettings()
        event_bus = AsyncMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.query_dataframe = AsyncMock(return_value=DataFrame())

        service = ForecastService(settings, location, event_bus, influxdb)

        await service.publish_forecast()

        # No events should be emitted when data is empty
        event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_forecast_emits_events(self):
        """Test publish_forecast emits MQTT and Forecast events."""
        settings = ForecastSettings(enable=True, retain=True)
        location = MockLocationSettings()
        event_bus = AsyncMock(spec=EventBus)
        influxdb = AsyncMock()

        # Create mock forecast data
        forecast_data = DataFrame({
            "_time": [
                datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
            ],
            "power": [1000, 1200],
            "energy": [1.0, 1.2],
        })
        forecast_data["_time"] = forecast_data["_time"].astype(
            f"datetime64[ns, {LOCAL_TZ}]"
        )

        influxdb.query_dataframe = AsyncMock(return_value=forecast_data)

        service = ForecastService(settings, location, event_bus, influxdb)

        await service.publish_forecast()

        # Should emit 2 events (MQTTPublishEvent and ForecastEvent)
        assert event_bus.emit.call_count == 2


class TestForecasterInit:
    """Tests for Forecaster initialization."""

    def test_forecaster_init(self):
        """Test Forecaster initialization."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        assert forecaster.typed == ForecasterType.ENERGY
        assert forecaster.location == location
        assert forecaster.enable_hyperparameter_tuning is False
        assert forecaster.model_pipeline is None

    def test_forecaster_init_with_hyperparameter_tuning(self):
        """Test Forecaster with hyperparameter tuning enabled."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True, hyperparametertuning=True)

        forecaster = Forecaster(ForecasterType.POWER, location, settings)

        assert forecaster.enable_hyperparameter_tuning is True

    def test_forecaster_is_trained_false_initially(self):
        """Test is_trained returns False when not trained."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        assert forecaster.is_trained is False

    def test_forecaster_is_trained_true_after_training(self):
        """Test is_trained returns True after training."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)
        forecaster.model_pipeline = MagicMock()

        assert forecaster.is_trained is True


class TestForecasterTrain:
    """Tests for Forecaster train method."""

    def test_train_raises_with_insufficient_data(self):
        """Test train raises when data has fewer than 60 rows."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        # Create dataframe with fewer than 60 rows
        data = DataFrame({
            "time": [datetime.now() for _ in range(30)],
            "energy": [100.0] * 30,
            "clouds": [50] * 30,
        })

        with pytest.raises(InvalidDataException) as exc_info:
            forecaster.train(data)

        assert "at least 60 hours" in exc_info.value.message

    def test_train_creates_pipeline(self):
        """Test train creates model pipeline."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        # Create dataframe with enough rows
        data = DataFrame({
            "time": [
                datetime.now(timezone.utc) + timedelta(hours=i) for i in range(100)
            ],
            "energy": [100.0 + i for i in range(100)],
            "power": [1000 + i * 10 for i in range(100)],
            "clouds": [50] * 100,
            "temp": [25.0] * 100,
            "humidity": [50] * 100,
            "pressure": [1013] * 100,
            "wind_speed": [5.0] * 100,
            "wind_deg": [180] * 100,
            "uvi": [5.0] * 100,
            "pop": [0.1] * 100,
            "weather_id": [800] * 100,
            "weather_main": ["Clear"] * 100,
        })
        data["time"] = data["time"].astype(f"datetime64[ns, {LOCAL_TZ}]")

        forecaster.train(data)

        assert forecaster.model_pipeline is not None
        assert forecaster.is_trained is True


class TestForecasterPredict:
    """Tests for Forecaster predict method."""

    @pytest.mark.asyncio
    async def test_predict_raises_when_not_trained(self):
        """Test predict raises when model not trained."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        data = DataFrame({"time": [datetime.now()], "energy": [100.0]})

        with pytest.raises(InvalidDataException) as exc_info:
            await forecaster.predict(data)

        assert "not been trained" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_predict_returns_predictions(self):
        """Test predict returns DataFrame with predictions."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        # Mock the pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.predict.return_value = [100.0, 150.0]
        forecaster.model_pipeline = mock_pipeline
        forecaster.training_completed.set()

        data = DataFrame({
            "time": [datetime.now(), datetime.now() + timedelta(hours=1)],
        })

        result = await forecaster.predict(data)

        assert "energy" in result.columns
        mock_pipeline.predict.assert_called_once()


class TestForecasterExtractUsedColumns:
    """Tests for Forecaster._extract_used_columns static method."""

    def test_extract_used_columns_with_list(self):
        """Test _extract_used_columns with list input."""
        features = ["col1", "col2", "col3"]
        columns = ["col1", "col3", "col4"]

        result = Forecaster._extract_used_columns(features, columns)

        assert result == ["col1", "col3"]

    def test_extract_used_columns_with_dict(self):
        """Test _extract_used_columns with dict input."""
        features = {"col1": 24, "col2": 12}
        columns = ["col1", "col3"]

        result = Forecaster._extract_used_columns(features, columns)

        assert result == ["col1"]

    def test_extract_used_columns_no_match(self):
        """Test _extract_used_columns with no matching columns."""
        features = ["col1", "col2"]
        columns = ["col3", "col4"]

        result = Forecaster._extract_used_columns(features, columns)

        assert result == []


class TestPFISelector:
    """Tests for PFISelector class."""

    def test_pfi_selector_init(self):
        """Test PFISelector initialization."""
        mock_estimator = MagicMock()

        selector = PFISelector(estimator=mock_estimator, n_repeats=5)

        assert selector.estimator == mock_estimator
        assert selector.n_repeats == 5

    def test_pfi_selector_transform_not_fitted_raises(self):
        """Test transform raises when not fitted."""
        mock_estimator = MagicMock()
        selector = PFISelector(estimator=mock_estimator)

        data = DataFrame({"col1": [1, 2, 3]})

        with pytest.raises(RuntimeError, match="not been fitted"):
            selector.transform(data)

    def test_pfi_selector_get_support_not_fitted_raises(self):
        """Test get_support raises when not fitted."""
        mock_estimator = MagicMock()
        selector = PFISelector(estimator=mock_estimator)

        with pytest.raises(RuntimeError, match="not been fitted"):
            selector.get_support()

    def test_pfi_selector_transform_returns_selected_features(self):
        """Test transform returns only important features."""
        mock_estimator = MagicMock()
        selector = PFISelector(estimator=mock_estimator)

        # Manually set important_features_ to simulate fitted state
        selector.important_features_ = pd.Index(["col1", "col3"])

        data = DataFrame({
            "col1": [1, 2, 3],
            "col2": [4, 5, 6],
            "col3": [7, 8, 9],
        })

        result = selector.transform(data)

        assert list(result.columns) == ["col1", "col3"]
        assert "col2" not in result.columns


class TestForecasterPreparePreprocessor:
    """Tests for Forecaster._prepare_preprocessor method."""

    def test_prepare_preprocessor_returns_column_transformer(self):
        """Test _prepare_preprocessor returns ColumnTransformer."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        columns = ["time", "clouds", "temp", "weather_id", "wind_deg"]
        preprocessor = forecaster._prepare_preprocessor(columns)

        assert isinstance(preprocessor, ColumnTransformer)


class TestForecasterPrepareModelPipeline:
    """Tests for Forecaster._prepare_model_pipeline method."""

    def test_prepare_model_pipeline_returns_pipeline(self):
        """Test _prepare_model_pipeline returns Pipeline."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        columns = ["time", "clouds", "temp"]
        pipeline = forecaster._prepare_model_pipeline(columns)

        assert isinstance(pipeline, Pipeline)

    def test_prepare_model_pipeline_has_steps(self):
        """Test _prepare_model_pipeline has required steps."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        columns = ["time", "clouds", "temp"]
        pipeline = forecaster._prepare_model_pipeline(columns)

        step_names = [name for name, _ in pipeline.steps]
        assert "preprocessor" in step_names
        assert "feature_selector" in step_names
        assert "model" in step_names


class TestForecastServiceWritePeriodsToInfluxDB:
    """Tests for ForecastService._write_periods_to_influxdb method."""

    @pytest.mark.asyncio
    async def test_write_periods_to_influxdb(self):
        """Test _write_periods_to_influxdb creates points."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.write_points = AsyncMock()

        service = ForecastService(settings, location, event_bus, influxdb)

        periods = DataFrame({
            "time": [
                datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
                datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
            ],
            "energy": [1.5, 2.0],
        })
        periods["time"] = periods["time"].astype(f"datetime64[ns, {LOCAL_TZ}]")

        await service._write_periods_to_influxdb(periods, ForecasterType.ENERGY)

        influxdb.write_points.assert_called_once()
        call_args = influxdb.write_points.call_args[0][0]
        assert len(call_args) == 2  # 2 points


class TestForecastServiceTrain:
    """Tests for ForecastService.train method."""

    @pytest.mark.asyncio
    async def test_train_queries_dataframe(self):
        """Test train queries training data from InfluxDB."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()

        # Create mock dataframe
        mock_df = DataFrame({
            "_time": [
                datetime.now(timezone.utc) + timedelta(hours=i) for i in range(100)
            ],
            "energy": [100.0 + i for i in range(100)],
            "power": [1000 + i * 10 for i in range(100)],
            "clouds": [50] * 100,
        })
        mock_df["_time"] = mock_df["_time"].astype(f"datetime64[ns, UTC]")

        influxdb.query_dataframe = AsyncMock(return_value=mock_df)

        service = ForecastService(settings, location, event_bus, influxdb)

        # Mock the training method to avoid actual ML training
        with patch.object(service, "training"):
            await service.train()

        influxdb.query_dataframe.assert_called_once_with("training_data")


class TestForecastServiceAddLastHourPvProduction:
    """Tests for ForecastService.add_last_hour_pv_production method."""

    @pytest.mark.asyncio
    async def test_add_last_hour_pv_production(self):
        """Test add_last_hour_pv_production adds production data."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        event_bus = MagicMock(spec=EventBus)
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(return_value={
            ForecasterType.POWER.target_column: 1234.5,
            ForecasterType.ENERGY.target_column: 1.567,
        })

        service = ForecastService(settings, location, event_bus, influxdb)

        training_data = {"temp": 25.0, "clouds": 20}

        result = await service.add_last_hour_pv_production(training_data)

        # Power is rounded using Python's built-in round()
        assert result[ForecasterType.POWER.target_column] == round(1234.5)
        # Energy is rounded to 2 decimal places
        assert result[ForecasterType.ENERGY.target_column] == 1.57


class TestForecasterHyperparameterTuning:
    """Tests for Forecaster hyperparameter tuning."""

    def test_hyperparametertuning_with_data(self):
        """Test _hyperparametertuning method."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True, hyperparametertuning=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        # Create enough data
        data = DataFrame({
            "time": [
                datetime.now(timezone.utc) + timedelta(hours=i) for i in range(100)
            ],
            "energy": [100.0 + i for i in range(100)],
            "clouds": [50] * 100,
            "temp": [25.0] * 100,
        })
        data["time"] = data["time"].astype(f"datetime64[ns, {LOCAL_TZ}]")

        y_vector = data["energy"]
        pipeline = forecaster._prepare_model_pipeline(data.columns.to_list())

        # This will do actual hyperparameter tuning (slow but tests the method)
        result = forecaster._hyperparametertuning(data, y_vector, pipeline)

        assert result is not None
