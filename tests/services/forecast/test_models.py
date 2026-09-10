"""Tests for forecast models module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from solaredge2mqtt.services.forecast.models import INTERVAL_MINUTES, Forecast

FORECAST_TIMEZONE = "Europe/Berlin"
PRODUCTION_THRESHOLD_WH = 500.0
LOCAL_MIDNIGHT_UTC = datetime(2024, 6, 14, 22, 0, tzinfo=timezone.utc)


class TestForecast:
    """Tests for Forecast class."""

    def make_energy_period(self) -> dict[datetime, int]:
        """48 hours of forecast data, keyed in UTC, starting at local midnight."""
        energy_period: dict[datetime, int] = {}
        for hour in range(48):
            local_hour = hour % 24
            # A bell curve over the local day: nothing at night, peak at noon.
            if 6 <= local_hour <= 18:
                energy = 1000 - abs(12 - local_hour) * 80
            else:
                energy = 0

            energy_period[self.at_local_hour(hour)] = energy

        return energy_period

    def make_forecast(self, **kwargs) -> Forecast:
        kwargs.setdefault("production_threshold_wh", PRODUCTION_THRESHOLD_WH)
        return Forecast.from_energy_period(
            self.make_energy_period(), timezone=FORECAST_TIMEZONE, **kwargs
        )

    def today(self) -> list[int]:
        return list(self.make_energy_period().values())[:24]

    def tomorrow(self) -> list[int]:
        return list(self.make_energy_period().values())[24:]

    def at_local_hour(self, hour: int) -> datetime:
        """`hour` hours after local midnight of the forecast's first day.

        22:00 UTC is midnight in Berlin's summer time, so both calendar days
        the aggregation splits on are complete.
        """
        return LOCAL_MIDNIGHT_UTC + timedelta(hours=hour)

    def test_forecast_creation(self):
        """Test Forecast creation."""
        forecast = self.make_forecast()

        assert len(forecast.energy_period) == 48
        assert forecast.interval_minutes == INTERVAL_MINUTES
        assert forecast.timezone == FORECAST_TIMEZONE

    def test_from_energy_period_mirrors_deprecated_power_period(self):
        """power_period is derived, not predicted, until it is removed."""
        forecast = self.make_forecast()

        assert forecast.power_period == forecast.energy_period
        assert forecast.power_period is not forecast.energy_period

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_today(self, mock_now):
        """Test energy_today computed field."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast()

        assert forecast.energy_today == sum(self.today())

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_today_remaining(self, mock_now):
        """Test energy_today_remaining computed field."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast()

        assert forecast.energy_today_remaining == sum(self.today()[12:])

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_current_hour(self, mock_now):
        """Test energy_current_hour computed field."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast()

        assert forecast.energy_current_hour == self.today()[12]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_next_hour_normal(self, mock_now):
        """Test energy_next_hour when not at midnight."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast()

        assert forecast.energy_next_hour == self.today()[13]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_next_hour_at_23(self, mock_now):
        """Test energy_next_hour at 23:00 returns tomorrow's first hour."""
        mock_now.return_value = self.at_local_hour(23)
        forecast = self.make_forecast()

        assert forecast.energy_next_hour == self.tomorrow()[0]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_tomorrow(self, mock_now):
        """Test energy_tomorrow computed field."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast()

        assert forecast.energy_tomorrow == sum(self.tomorrow())

    def test_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        ha_info = self.make_forecast().homeassistant_device_info()

        assert ha_info["name"] == "SolarEdge2MQTT Forecast"
        assert "manufacturer" in ha_info

    def test_model_json_schema_excludes_period_fields(self):
        """Test model_json_schema excludes power_period and energy_period."""
        schema = Forecast.model_json_schema()

        assert "power_period" not in schema["properties"]
        assert "energy_period" not in schema["properties"]

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_none_without_battery(self, mock_now):
        """Test optimal start time is None when no battery energy is needed."""
        mock_now.return_value = self.at_local_hour(10)
        forecast = self.make_forecast(battery_charge_needed_wh=None)

        assert forecast.battery_charge_optimal_start_time is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_none_when_already_charged(
        self, mock_now
    ):
        """Test optimal start time is None when no energy is needed (0 Wh)."""
        mock_now.return_value = self.at_local_hour(10)
        forecast = self.make_forecast(battery_charge_needed_wh=0)

        assert forecast.battery_charge_optimal_start_time is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_picks_strongest_slot(self, mock_now):
        """Test optimal start time picks the earliest of the strongest slots."""
        mock_now.return_value = self.at_local_hour(10)
        # The peak slot (1000 Wh) is at 12:00 local, which alone covers the need.
        forecast = self.make_forecast(battery_charge_needed_wh=1000)

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(12)

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_skips_passed_slots(self, mock_now):
        """Test optimal start time ignores slots that are already in the past."""
        # Today's 12:00 peak (1000 Wh) has already passed at 13:00, so 13:00
        # (920 Wh) and 14:00 (840 Wh) together cover the need.
        mock_now.return_value = self.at_local_hour(13)
        forecast = self.make_forecast(battery_charge_needed_wh=1000)

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(13)

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_ignores_tomorrow(self, mock_now):
        """Tomorrow's production must not be proposed as today's start time."""
        # After sunset today's remaining slots are all 0 Wh, while tomorrow
        # would easily cover the need.
        mock_now.return_value = self.at_local_hour(19)
        forecast = self.make_forecast(battery_charge_needed_wh=1000)

        assert forecast.battery_charge_optimal_start_time is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_none_when_forecast_is_over(
        self, mock_now
    ):
        """No slot lies ahead once the whole forecast window has passed."""
        mock_now.return_value = self.at_local_hour(48)
        forecast = self.make_forecast(battery_charge_needed_wh=1000)

        assert forecast.battery_charge_optimal_start_time is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_optimal_start_time_now_when_unreachable(self, mock_now):
        """An unreachable target starts as early as possible, right now."""
        mock_now.return_value = self.at_local_hour(10)
        forecast = self.make_forecast(battery_charge_needed_wh=10_000_000)

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(10)
        assert forecast.battery_charge_target_reachable is False

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_peak_today_finds_strongest_slot(self, mock_now):
        """The peak covers the whole day, not only what is still ahead."""
        mock_now.return_value = self.at_local_hour(18)
        forecast = self.make_forecast()

        assert forecast.energy_peak_today == 1000
        assert forecast.energy_peak_time_today == self.at_local_hour(12)

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_peak_today_prefers_the_earlier_of_equal_slots(self, mock_now):
        """A flat-topped day reports the first of its equal maxima."""
        mock_now.return_value = self.at_local_hour(12)
        energy_period = self.make_energy_period()
        energy_period[self.at_local_hour(14)] = 1000
        forecast = Forecast.from_energy_period(
            energy_period,
            timezone=FORECAST_TIMEZONE,
            production_threshold_wh=PRODUCTION_THRESHOLD_WH,
        )

        assert forecast.energy_peak_time_today == self.at_local_hour(12)

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_peak_today_none_without_production(self, mock_now):
        """A day the forecast does not cover has no peak."""
        mock_now.return_value = self.at_local_hour(72)
        forecast = self.make_forecast()

        assert forecast.energy_peak_today == 0
        assert forecast.energy_peak_time_today is None

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_average_and_median_today(self, mock_now):
        """Every producing hour counts once the threshold is out of the way."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast(production_threshold_wh=0)

        assert forecast.energy_average_today == 742
        assert forecast.energy_median_today == 760

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_average_and_median_today_respect_threshold(self, mock_now):
        """The weak hours around sunrise and sunset drop out."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast(production_threshold_wh=700)

        assert forecast.energy_average_today == 863
        assert forecast.energy_median_today == 840

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_energy_average_and_median_today_without_production(self, mock_now):
        """No hour clears a threshold above the peak."""
        mock_now.return_value = self.at_local_hour(12)
        forecast = self.make_forecast(production_threshold_wh=2000)

        assert forecast.energy_average_today == 0
        assert forecast.energy_median_today == 0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_duration_counts_selected_slots(self, mock_now):
        """The peak slot alone covers the need, so one hour of charging."""
        mock_now.return_value = self.at_local_hour(10)
        forecast = self.make_forecast(battery_charge_needed_wh=1000)

        assert forecast.battery_charge_duration == 1.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_duration_spans_several_slots(self, mock_now):
        """After the peak has passed two slots are needed for the same energy."""
        mock_now.return_value = self.at_local_hour(13)
        forecast = self.make_forecast(battery_charge_needed_wh=1000)

        assert forecast.battery_charge_duration == 2.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_battery_charge_duration_none_without_need(self, mock_now):
        """Without a battery there is no window and no duration."""
        mock_now.return_value = self.at_local_hour(10)
        forecast = self.make_forecast()

        assert forecast.battery_charge_duration is None
        assert forecast.battery_charge_target_reachable is None

    def make_example_day(self, overrides: dict[int, int] | None = None):
        shape = {
            8: 3000,
            9: 5000,
            10: 5400,
            11: 5300,
            12: 5350,
            13: 6000,
            14: 7000,
            15: 6100,
            16: 5300,
        }
        shape.update(overrides or {})

        return {self.at_local_hour(hour): shape.get(hour, 0) for hour in range(24)}

    def make_example_forecast(self, overrides=None, **kwargs) -> Forecast:
        kwargs.setdefault("production_threshold_wh", PRODUCTION_THRESHOLD_WH)
        return Forecast.from_energy_period(
            self.make_example_day(overrides), timezone=FORECAST_TIMEZONE, **kwargs
        )

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_grows_around_the_peak(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        forecast = self.make_example_forecast(battery_charge_needed_wh=20_000)

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(13)
        assert forecast.battery_charge_duration == 4.0
        assert forecast.battery_charge_target_reachable is True

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_respects_the_charge_power_cap(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        forecast = self.make_example_forecast(
            battery_charge_needed_wh=20_000,
            battery_charge_slot_cap_wh=5435,
        )

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(13)
        assert forecast.battery_charge_duration == 4.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_cap_widens_the_window(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        uncapped = self.make_example_forecast(battery_charge_needed_wh=13_000)
        capped = self.make_example_forecast(
            battery_charge_needed_wh=13_000,
            battery_charge_slot_cap_wh=5435,
        )

        assert uncapped.battery_charge_duration == 2.0
        assert capped.battery_charge_duration == 3.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_starts_at_the_peak_when_it_suffices(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        forecast = self.make_example_forecast(battery_charge_needed_wh=7000)

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(14)
        assert forecast.battery_charge_duration == 1.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_prefers_the_later_slot_on_overflow(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        forecast = self.make_example_forecast(battery_charge_needed_wh=14_000)

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(14)
        assert forecast.battery_charge_duration == 3.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_prefers_the_later_slot_on_a_tie(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        forecast = self.make_example_forecast(
            {13: 6100}, battery_charge_needed_wh=13_100
        )

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(14)
        assert forecast.battery_charge_duration == 2.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_stops_at_a_slot_below_the_threshold(self, mock_now):
        mock_now.return_value = self.at_local_hour(8)
        forecast = self.make_example_forecast(
            {15: 400}, battery_charge_needed_wh=20_000
        )

        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(11)
        assert forecast.battery_charge_duration == 4.0

    @patch("solaredge2mqtt.services.forecast.models.Forecast._now")
    def test_charge_window_anchors_on_the_strongest_remaining_slot(self, mock_now):
        mock_now.return_value = self.at_local_hour(15)
        forecast = self.make_example_forecast(battery_charge_needed_wh=6000)

        assert forecast.energy_peak_time_today == self.at_local_hour(14)
        assert forecast.battery_charge_optimal_start_time == self.at_local_hour(15)
        assert forecast.battery_charge_duration == 1.0
