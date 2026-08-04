"""Tests for forecast models module."""

from datetime import datetime, timezone
from unittest.mock import patch

from solaredge2mqtt.services.forecast.models import Forecast


class TestForecast:
    """Tests for Forecast class."""

    def make_forecast_data(self) -> dict:
        """Create forecast data for testing."""
        # Create 48 hours of forecast data (24 today + 24 tomorrow)
        power_period = {}
        energy_period = {}

        base_time = datetime(2024, 6, 15, 0, 0, tzinfo=timezone.utc)

        for hour in range(48):
            hour_time = datetime(
                base_time.year,
                base_time.month,
                base_time.day + (hour // 24),
                hour % 24,
                0,
                tzinfo=timezone.utc,
            )

            # Simulate a bell curve for power (0 at night, peak at noon)
            if 6 <= (hour % 24) <= 18:
                power = 1000 - abs(12 - (hour % 24)) * 80
            else:
                power = 0

            power_period[hour_time] = power
            energy_period[hour_time] = power  # Energy in Wh for the hour

        return {"power_period": power_period, "energy_period": energy_period}

    def test_forecast_creation(self):
        """Test Forecast creation."""
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        assert forecast.power_period is not None
        assert forecast.energy_period is not None
        assert len(forecast.power_period) == 48
        assert len(forecast.energy_period) == 48

    @patch("solaredge2mqtt.services.forecast.models.Forecast._current_hour")
    def test_energy_today(self, mock_hour):
        """Test energy_today computed field."""
        mock_hour.return_value = 12
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        # Sum of first 24 hours
        expected_today = sum(list(data["energy_period"].values())[:24])
        assert forecast.energy_today == expected_today

    @patch("solaredge2mqtt.services.forecast.models.Forecast._current_hour")
    def test_energy_today_remaining(self, mock_hour):
        """Test energy_today_remaining computed field."""
        mock_hour.return_value = 12
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        # Sum from hour 12 to 23
        values = list(data["energy_period"].values())[:24]
        expected_remaining = sum(values[12:])
        assert forecast.energy_today_remaining == expected_remaining

    @patch("solaredge2mqtt.services.forecast.models.Forecast._current_hour")
    def test_energy_current_hour(self, mock_hour):
        """Test energy_current_hour computed field."""
        mock_hour.return_value = 12
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        values = list(data["energy_period"].values())[:24]
        assert forecast.energy_current_hour == values[12]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._current_hour")
    def test_energy_next_hour_normal(self, mock_hour):
        """Test energy_next_hour when not at midnight."""
        mock_hour.return_value = 12
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        values = list(data["energy_period"].values())[:24]
        assert forecast.energy_next_hour == values[13]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._current_hour")
    def test_energy_next_hour_at_23(self, mock_hour):
        """Test energy_next_hour at 23:00 returns tomorrow's first hour."""
        mock_hour.return_value = 23
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        tomorrow_values = list(data["energy_period"].values())[24:]
        assert forecast.energy_next_hour == tomorrow_values[0]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._current_hour")
    def test_energy_tomorrow(self, mock_hour):
        """Test energy_tomorrow computed field."""
        mock_hour.return_value = 12
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        # Sum of hours 24-47
        expected_tomorrow = sum(list(data["energy_period"].values())[24:])
        assert forecast.energy_tomorrow == expected_tomorrow

    def test_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        data = self.make_forecast_data()
        forecast = Forecast(**data)

        ha_info = forecast.homeassistant_device_info()

        assert ha_info["name"] == "SolarEdge2MQTT Forecast"
        assert "manufacturer" in ha_info

    def test_model_json_schema_excludes_period_fields(self):
        """Test model_json_schema excludes power_period and energy_period."""
        schema = Forecast.model_json_schema()

        assert "power_period" not in schema["properties"]
        assert "energy_period" not in schema["properties"]

    def test_current_hour_is_valid_range(self):
        """Test _current_hour returns a valid hour value."""
        hour = Forecast._current_hour()  # noqa: SLF001
        assert 0 <= hour <= 23

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_none_without_battery(self, mock_now):
        """Test optimal start time is None when no battery energy is needed."""
        mock_now.return_value = datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        data = self.make_forecast_data()
        forecast = Forecast(**data, battery_charge_needed_wh=None)

        assert forecast.battery_charge_optimal_start_time is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_none_when_already_charged(
        self, mock_now
    ):
        """Test optimal start time is None when no energy is needed (0 Wh)."""
        mock_now.return_value = datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        data = self.make_forecast_data()
        forecast = Forecast(**data, battery_charge_needed_wh=0)

        assert forecast.battery_charge_optimal_start_time is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_picks_strongest_slot(self, mock_now):
        """Test optimal start time picks the earliest of the strongest slots."""
        mock_now.return_value = datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        data = self.make_forecast_data()
        # The peak slot (1000 Wh) is at 12:00 today, which alone covers the need.
        forecast = Forecast(**data, battery_charge_needed_wh=1000)

        assert forecast.battery_charge_optimal_start_time == datetime(
            2024, 6, 15, 12, 0, tzinfo=timezone.utc
        )

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_skips_passed_slots(self, mock_now):
        """Test optimal start time ignores slots that are already in the past."""
        # Today's 12:00 peak (1000 Wh) has already passed at 13:00.
        mock_now.return_value = datetime(2024, 6, 15, 13, 0, tzinfo=timezone.utc)
        data = self.make_forecast_data()
        forecast = Forecast(**data, battery_charge_needed_wh=1000)

        assert forecast.battery_charge_optimal_start_time == datetime(
            2024, 6, 16, 12, 0, tzinfo=timezone.utc
        )

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_none_when_unreachable(self, mock_now):
        """Test optimal start time is None if forecast can't cover the need."""
        mock_now.return_value = datetime(2024, 6, 15, 10, 0, tzinfo=timezone.utc)
        data = self.make_forecast_data()
        forecast = Forecast(**data, battery_charge_needed_wh=10_000_000)

        assert forecast.battery_charge_optimal_start_time is None
