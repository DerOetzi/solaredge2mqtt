"""Tests for ForecastService with mocked ML dependencies."""

from datetime import datetime, timedelta, timezone
from datetime import datetime as dt_class
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pandas import DataFrame

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.settings.models import LocationSettings
from solaredge2mqtt.services.forecast.models import ForecasterType
from solaredge2mqtt.services.forecast.service import (
    LOCAL_TZ,
    Forecaster,
    ForecastService,
)
from solaredge2mqtt.services.forecast.settings import ForecastSettings
from solaredge2mqtt.services.weather.events import WeatherUpdateEvent
from solaredge2mqtt.services.weather.models import (
    OpenWeatherMapCondition,
    OpenWeatherMapForecastData,
)


@pytest.fixture(autouse=True)
def mock_memory():
    """Mock joblib Memory to avoid file system operations."""
    with patch("pvlearn.forecaster.Memory") as mock:
        # Make Memory return None (disabled) instead of a MagicMock
        mock.return_value = None
        yield mock


class MockLocationSettings(LocationSettings):
    """Mock LocationSettings for testing."""

    def __init__(self, latitude=52.52, longitude=13.405):
        super().__init__(latitude=latitude, longitude=longitude)


class MockOpenWeatherMapForecastData(OpenWeatherMapForecastData):
    """Mock OpenWeatherMapForecastData for testing."""

    def __init__(self, hour=12, year=2024, month=6, day=15):
        if hour > 23:
            day += 1
            hour -= 24

        super().__init__(
            dt=datetime(year, month, day, hour, tzinfo=timezone.utc),
            temp=25.0,
            humidity=50,
            clouds=20,
            pressure=1013,
            wind_speed=5.0,
            wind_deg=180,
            uvi=5.0,
            pop=0.1,
            weather=[
                OpenWeatherMapCondition(
                    id=800, main="Clear", description="clear sky", icon="01d"
                )
            ],
        )


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
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        assert service.settings == settings
        assert service.location == location
        assert service.influxdb == influxdb
        assert service.last_weather_forecast is None
        assert service.last_hour_forecast is None

    def test_forecast_service_creates_forecasters(self):
        """Test ForecastService creates forecasters for each type."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        assert ForecasterType.ENERGY in service.forecasters
        assert ForecasterType.POWER in service.forecasters
        assert isinstance(service.forecasters[ForecasterType.ENERGY], Forecaster)
        assert isinstance(service.forecasters[ForecasterType.POWER], Forecaster)

    def test_forecast_service_subscribes_events(self, mock_event_bus):
        """Test ForecastService registers event handlers."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        mock_event_bus.register.assert_called_once_with(service)


class TestForecastServiceBattery:
    """Tests for ForecastService battery tracking and charge need calculation."""

    def make_service(self, **settings_kwargs) -> ForecastService:
        settings = ForecastSettings(enable=True, **settings_kwargs)
        location = MockLocationSettings()
        influxdb = MagicMock()
        return ForecastService(settings, location, influxdb)

    def make_battery(self, rated_energy: float, state_of_charge: float) -> MagicMock:
        battery = MagicMock()
        battery.rated_energy = rated_energy
        battery.state_of_charge = state_of_charge
        return battery

    @pytest.mark.asyncio
    async def test_battery_update_sums_capacity_and_stored_energy(self):
        """battery_update should sum capacity/stored energy across units."""
        from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent

        service = self.make_service()

        unit_leader = MagicMock()
        unit_leader.batteries = {
            # 9200 Wh capacity at 50% SOC -> 4600 Wh stored
            "battery0": self.make_battery(rated_energy=9200, state_of_charge=50.0)
        }
        unit_follower = MagicMock()
        unit_follower.batteries = {
            # 4600 Wh capacity at 25% SOC -> 1150 Wh stored
            "battery0": self.make_battery(rated_energy=4600, state_of_charge=25.0)
        }

        event = ModbusUnitsReadEvent(
            {"leader": unit_leader, "follower1": unit_follower}
        )
        await service.battery_update(event)

        assert service.last_battery_capacity_wh == 13800
        assert service.last_battery_stored_energy_wh == pytest.approx(5750)

    @pytest.mark.asyncio
    async def test_battery_update_resets_when_no_battery_present(self):
        """battery_update should reset stored values when no battery is found."""
        from solaredge2mqtt.services.modbus.events import ModbusUnitsReadEvent

        service = self.make_service()
        service.last_battery_capacity_wh = 9200
        service.last_battery_stored_energy_wh = 4000

        unit = MagicMock()
        unit.batteries = {}

        event = ModbusUnitsReadEvent({"leader": unit})
        await service.battery_update(event)

        assert service.last_battery_capacity_wh is None
        assert service.last_battery_stored_energy_wh is None

    def test_battery_charge_needed_wh_none_without_battery(self):
        """battery_charge_needed_wh should be None without known battery capacity."""
        service = self.make_service()

        assert service.battery_charge_needed_wh() is None

    def test_battery_charge_needed_wh_computes_deficit(self):
        """battery_charge_needed_wh applies target SOC and charge efficiency."""
        service = self.make_service(
            battery_target_soc=98.0, battery_charge_efficiency=0.92
        )
        service.last_battery_capacity_wh = 9200
        service.last_battery_stored_energy_wh = 4600

        target_energy_wh = 9200 * 98.0 / 100
        expected = (target_energy_wh - 4600) / 0.92

        assert service.battery_charge_needed_wh() == pytest.approx(expected)

    def test_battery_charge_needed_wh_zero_when_target_already_met(self):
        """battery_charge_needed_wh returns 0 if battery is already at/above target."""
        service = self.make_service(battery_target_soc=50.0)
        service.last_battery_capacity_wh = 9200
        service.last_battery_stored_energy_wh = 9000

        assert service.battery_charge_needed_wh() == 0.0


class TestForecastServiceWeatherUpdate:
    """Tests for ForecastService weather_update method."""

    @pytest.mark.asyncio
    async def test_weather_update_stores_forecast(self):
        """Test weather_update stores the weather forecast."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        weather_data = MockWeatherData()
        event = MagicMock(spec=WeatherUpdateEvent)
        event.weather = weather_data

        await service.weather_update(event)

        assert service.last_weather_forecast == weather_data.hourly

    @pytest.mark.asyncio
    async def test_weather_update_initializes_last_hour_forecast(self):
        """Test weather_update initializes last_hour_forecast dict."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        weather_data = MockWeatherData()
        event = MagicMock(spec=WeatherUpdateEvent)
        event.weather = weather_data

        await service.weather_update(event)

        assert service.last_hour_forecast is not None
        assert isinstance(service.last_hour_forecast, dict)

    @pytest.mark.asyncio
    async def test_weather_update_stores_current_hour(self):
        """Test weather_update stores current hour's forecast."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        # Use the current UTC datetime to construct forecast data so the
        # local-hour conversion inside the service matches what we expect.
        now_utc = dt_class.now(timezone.utc)
        now_local = now_utc.astimezone(LOCAL_TZ)
        current_hour = now_local.hour
        hourly_data = [
            MockOpenWeatherMapForecastData(
                hour=now_utc.hour,
                year=now_utc.year,
                month=now_utc.month,
                day=now_utc.day,
            )
        ]
        weather_data = MockWeatherData(hourly=hourly_data)
        event = MagicMock(spec=WeatherUpdateEvent)
        event.weather = weather_data

        await service.weather_update(event)

        assert service.last_hour_forecast is not None
        assert current_hour in service.last_hour_forecast
        assert service.last_hour_forecast[current_hour] == hourly_data[0]

    @pytest.mark.asyncio
    async def test_weather_update_cleans_old_hours(self):
        """Test weather_update removes old hour forecasts."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)

        # Pre-populate with old hours
        service.last_hour_forecast = {
            0: MagicMock(),
            5: MagicMock(),
            10: MagicMock(),
        }

        # Update with current hour 12
        hourly_data = [MockOpenWeatherMapForecastData(hour=12)]
        weather_data = MockWeatherData(hourly=hourly_data)
        event = MagicMock(spec=WeatherUpdateEvent)
        event.weather = weather_data

        with patch("solaredge2mqtt.services.forecast.service.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 12
            mock_dt.now.return_value = mock_now
            mock_now.astimezone.return_value = mock_now
            mock_now.__sub__ = lambda self, x: MagicMock(spec=["hour"], hour=11)

            await service.weather_update(event)

        # Old hours (0, 5, 10) should be removed, only 12 and 11 kept
        assert 0 not in service.last_hour_forecast
        assert 5 not in service.last_hour_forecast
        assert 10 not in service.last_hour_forecast

    @pytest.mark.asyncio
    async def test_weather_update_writes_last_hour_training_data(self):
        """weather_update should trigger training write for previous hour."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()

        service = ForecastService(settings, location, influxdb)
        service.write_new_training_data = AsyncMock()

        hourly_data = [MockOpenWeatherMapForecastData(hour=11)]
        weather_data = MockWeatherData(hourly=hourly_data)
        event = MagicMock(spec=WeatherUpdateEvent)
        event.weather = weather_data

        with patch("solaredge2mqtt.services.forecast.service.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.hour = 12
            mock_last_hour = MagicMock()
            mock_last_hour.hour = 11

            mock_dt.now.return_value = mock_now
            mock_now.astimezone.return_value = mock_now
            mock_now.__sub__.return_value = mock_last_hour

            await service.weather_update(event)

        service.write_new_training_data.assert_awaited_once_with(hourly_data[0])


class TestForecastServiceWriteTrainingData:
    """Tests for ForecastService write_new_training_data method."""

    @pytest.mark.asyncio
    async def test_write_new_training_data_calls_influxdb(self):
        """Test write_new_training_data writes to InfluxDB."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(
            return_value={
                "power": 1000.0,
                "energy": 5.0,
            }
        )
        influxdb.write_point = AsyncMock()

        service = ForecastService(settings, location, influxdb)

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
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(return_value=None)

        service = ForecastService(settings, location, influxdb)

        weather_forecast = MockOpenWeatherMapForecastData(hour=11)

        with pytest.raises(InvalidDataException) as exc_info:
            await service.write_new_training_data(weather_forecast)

        assert "Missing production data" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_write_new_training_data_triggers_train_at_20min(self):
        """Test write_new_training_data triggers training at minute 20."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(
            return_value={
                "power": 1000.0,
                "energy": 5.0,
            }
        )
        influxdb.write_point = AsyncMock()
        influxdb.query_dataframe = AsyncMock(return_value=DataFrame())

        service = ForecastService(settings, location, influxdb)
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
        influxdb = AsyncMock()

        service = ForecastService(settings, location, influxdb)

        # Mock forecasters as trained
        for forecaster in service.forecasters.values():
            forecaster.model_pipeline = MagicMock()

        with pytest.raises(InvalidDataException) as exc_info:
            await service.forecast_loop(MagicMock())

        assert "Missing weather forecast" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_forecast_loop_triggers_training_if_not_trained(self):
        """Test forecast_loop triggers training when models not trained."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()
        influxdb.query_dataframe = AsyncMock(return_value=DataFrame())
        influxdb.write_points = AsyncMock()

        service = ForecastService(settings, location, influxdb)

        # Create mock train that sets up forecasters as trained
        def mock_train_impl():
            """Mock train that sets up forecasters as trained."""
            for forecaster in service.forecasters.values():
                mock_pipeline = MagicMock()
                # Return realistic predictions: [1000, 1200]
                mock_pipeline.predict.return_value = [1000.0, 1200.0]
                forecaster.model_pipeline = mock_pipeline
                forecaster.training_completed.set()

        service.train = AsyncMock(side_effect=mock_train_impl)

        # Forecasters not trained initially (model_pipeline is None)
        service.last_weather_forecast = [
            MockOpenWeatherMapForecastData(),
            MockOpenWeatherMapForecastData(hour=13),
        ]

        # forecast_loop should call train and then proceed
        await service.forecast_loop(MagicMock())

        service.train.assert_called_once()


class TestForecastServicePublishForecast:
    """Tests for ForecastService publish_forecast method."""

    @pytest.mark.asyncio
    async def test_publish_forecast_empty_data(self, mock_event_bus):
        """Test publish_forecast does nothing with empty data."""
        settings = ForecastSettings(enable=True, retain=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()
        influxdb.query_dataframe = AsyncMock(return_value=DataFrame())

        service = ForecastService(settings, location, influxdb)

        await service.publish_forecast()

        # No events should be emitted when data is empty
        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_forecast_emits_events(self, mock_event_bus):
        """Test publish_forecast emits MQTT and Forecast events."""
        settings = ForecastSettings(enable=True, retain=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()

        # Create mock forecast data
        forecast_data = DataFrame(
            {
                "_time": [
                    datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
                    datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
                ],
                "power": [1000, 1200],
                "energy": [1.0, 1.2],
            }
        )
        forecast_data["_time"] = forecast_data["_time"].dt.tz_convert(LOCAL_TZ)

        influxdb.query_dataframe = AsyncMock(return_value=forecast_data)

        service = ForecastService(settings, location, influxdb)

        await service.publish_forecast()

        # Should emit 2 events (MQTTPublishEvent and ForecastEvent)
        assert mock_event_bus.emit.call_count == 2

    @pytest.mark.asyncio
    async def test_publish_forecast_includes_battery_charge_needed_wh(
        self, mock_event_bus
    ):
        """Test publish_forecast forwards the computed battery charge need."""
        settings = ForecastSettings(
            enable=True, battery_target_soc=98.0, battery_charge_efficiency=0.92
        )
        location = MockLocationSettings()
        influxdb = AsyncMock()

        forecast_data = DataFrame(
            {
                "_time": [datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)],
                "power": [1000],
                "energy": [1.0],
            }
        )
        forecast_data["_time"] = forecast_data["_time"].dt.tz_convert(LOCAL_TZ)
        influxdb.query_dataframe = AsyncMock(return_value=forecast_data)

        service = ForecastService(settings, location, influxdb)
        service.last_battery_capacity_wh = 9200
        service.last_battery_stored_energy_wh = 4600

        await service.publish_forecast()

        mqtt_event = mock_event_bus.emit.call_args_list[0].args[0]
        expected = (9200 * 98.0 / 100 - 4600) / 0.92
        assert mqtt_event.payload.battery_charge_needed_wh == pytest.approx(expected)

    @pytest.mark.asyncio
    async def test_publish_forecast_raises_on_invalid_time(self):
        """publish_forecast should reject non-datetime time values."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()

        forecast_data = DataFrame(
            {
                "_time": [datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)],
                "power": [1000.0],
                "energy": [1.0],
            }
        )
        influxdb.query_dataframe = AsyncMock(return_value=forecast_data)

        service = ForecastService(settings, location, influxdb)
        with patch.object(
            forecast_data,
            "iterrows",
            return_value=iter(
                [
                    (
                        0,
                        {
                            "time": "invalid",
                            "power": 1000.0,
                            "energy": 1.0,
                        },
                    )
                ]
            ),
        ):
            with pytest.raises(InvalidDataException):
                await service.publish_forecast()

    @pytest.mark.asyncio
    async def test_publish_forecast_raises_on_invalid_power(self):
        """publish_forecast should reject non-numeric power values."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()

        forecast_data = DataFrame(
            {
                "_time": [datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)],
                "power": ["invalid"],
                "energy": [1.0],
            }
        )
        influxdb.query_dataframe = AsyncMock(return_value=forecast_data)

        service = ForecastService(settings, location, influxdb)
        with pytest.raises(InvalidDataException):
            await service.publish_forecast()

    @pytest.mark.asyncio
    async def test_publish_forecast_raises_on_invalid_energy(self):
        """publish_forecast should reject non-numeric energy values."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()

        forecast_data = DataFrame(
            {
                "_time": [datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)],
                "power": [1000.0],
                "energy": ["invalid"],
            }
        )
        influxdb.query_dataframe = AsyncMock(return_value=forecast_data)

        service = ForecastService(settings, location, influxdb)
        with pytest.raises(InvalidDataException):
            await service.publish_forecast()


class TestForecastServiceWritePeriodsToInfluxDB:
    """Tests for ForecastService._write_periods_to_influxdb method."""

    @pytest.mark.asyncio
    async def test_write_periods_to_influxdb(self):
        """Test _write_periods_to_influxdb creates points."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()
        influxdb.write_points = AsyncMock()

        service = ForecastService(settings, location, influxdb)

        periods = DataFrame(
            {
                "time": [
                    datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc),
                    datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc),
                ],
                "energy": [1.5, 2.0],
            }
        )
        periods["time"] = periods["time"].dt.tz_convert(LOCAL_TZ)

        await service._write_periods_to_influxdb(periods, ForecasterType.ENERGY)

        influxdb.write_points.assert_called_once()
        call_args = influxdb.write_points.call_args[0][0]
        assert len(call_args) == 2  # 2 points

    @pytest.mark.asyncio
    async def test_write_periods_to_influxdb_raises_on_invalid_time(self):
        """_write_periods_to_influxdb should reject non-datetime values."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()

        service = ForecastService(settings, location, influxdb)
        periods = DataFrame({"time": ["invalid"], "energy": [1.5]})

        with pytest.raises(InvalidDataException):
            await service._write_periods_to_influxdb(periods, ForecasterType.ENERGY)


class TestForecastServiceTrain:
    """Tests for ForecastService.train method."""

    @pytest.mark.asyncio
    async def test_train_queries_dataframe(self):
        """Test train queries training data from InfluxDB."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()

        # Create mock dataframe
        mock_df = DataFrame(
            {
                "_time": [
                    datetime.now(timezone.utc) + timedelta(hours=i) for i in range(100)
                ],
                "energy": [100.0 + i for i in range(100)],
                "power": [1000 + i * 10 for i in range(100)],
                "clouds": [50] * 100,
            }
        )
        mock_df["_time"] = mock_df["_time"].astype("datetime64[ns, UTC]")

        influxdb.query_dataframe = AsyncMock(return_value=mock_df)

        service = ForecastService(settings, location, influxdb)

        # Mock the training method to avoid actual ML training
        with patch.object(service, "training"):
            await service.train()

        influxdb.query_dataframe.assert_called_once_with("training_data")

    def test_training_calls_each_forecaster(self):
        """training should dispatch data to each forecaster."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = MagicMock()
        service = ForecastService(settings, location, influxdb)

        first = MagicMock()
        second = MagicMock()
        service.forecasters = {
            ForecasterType.ENERGY: first,
            ForecasterType.POWER: second,
        }

        data = DataFrame({"energy": [1.0], "power": [100.0]})
        service.training(data)

        first.train.assert_called_once_with(data)
        second.train.assert_called_once_with(data)


class TestForecastServiceAddLastHourPvProduction:
    """Tests for ForecastService.add_last_hour_pv_production method."""

    @pytest.mark.asyncio
    async def test_add_last_hour_pv_production(self):
        """Test add_last_hour_pv_production adds production data."""
        settings = ForecastSettings(enable=True)
        location = MockLocationSettings()
        influxdb = AsyncMock()
        influxdb.query_first = AsyncMock(
            return_value={
                ForecasterType.POWER.target_column: 1234.5,
                ForecasterType.ENERGY.target_column: 1.567,
            }
        )

        service = ForecastService(settings, location, influxdb)

        training_data = {"temp": 25.0, "clouds": 20}

        result = await service.add_last_hour_pv_production(training_data)

        # Power is rounded using Python's built-in round()
        assert result[ForecasterType.POWER.target_column] == round(1234.5)
        # Energy is rounded to 2 decimal places
        assert result[ForecasterType.ENERGY.target_column] == pytest.approx(1.57)
