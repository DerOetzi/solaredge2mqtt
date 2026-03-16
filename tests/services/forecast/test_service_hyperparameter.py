from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from pandas import DataFrame

from solaredge2mqtt.core.settings.models import LocationSettings
from solaredge2mqtt.services.forecast.models import ForecasterType
from solaredge2mqtt.services.forecast.service import LOCAL_TZ, Forecaster
from solaredge2mqtt.services.forecast.settings import ForecastSettings


@pytest.fixture(autouse=True)
def mock_memory():
    """Mock joblib Memory to avoid file system operations."""
    with patch(
        "solaredge2mqtt.services.forecast.service.Memory"
    ) as mock:
        # Make Memory return None (disabled) instead of a MagicMock
        mock.return_value = None
        yield mock


class MockLocationSettings(LocationSettings):
    """Mock LocationSettings for testing."""

    def __init__(self, latitude=52.52, longitude=13.405):
        super().__init__(latitude=latitude, longitude=longitude)


class TestForecasterHyperparameterTuning:
    """Tests for Forecaster hyperparameter tuning."""

    @pytest.mark.slow
    def test_hyperparametertuning_with_data(self):
        """Test _hyperparametertuning method."""
        location = MockLocationSettings()
        settings = ForecastSettings(enable=True, hyperparametertuning=True)

        forecaster = Forecaster(ForecasterType.ENERGY, location, settings)

        # Create enough data
        data = DataFrame({
            "time": [
                datetime.now(timezone.utc) + timedelta(hours=i)
                for i in range(100)
            ],
            "energy": [100.0 + i for i in range(100)],
            "clouds": [50] * 100,
            "temp": [25.0] * 100,
        })
        data["time"] = data["time"].dt.tz_convert(LOCAL_TZ)

        y_vector = data["energy"]
        x_data = data.drop(columns=["energy"])
        pipeline = forecaster._prepare_model_pipeline(x_data.columns.to_list())

        # This will do actual hyperparameter tuning (slow but tests the method)
        result = forecaster._hyperparametertuning(x_data, y_vector, pipeline)

        assert result is not None
