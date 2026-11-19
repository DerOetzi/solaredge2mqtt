"""Tests for energy settings module."""

import pytest
import yaml
from pydantic import ValidationError

from solaredge2mqtt.services.energy.settings import (
    EnergySettings,
    PriceScheduleEntry,
    PriceSettings,
)


class TestPriceSettings:
    """Tests for PriceSettings class."""

    def test_price_settings_defaults(self):
        """Test PriceSettings default values."""
        settings = PriceSettings()

        assert settings.consumption is None
        assert settings.delivery is None
        assert settings.currency is None

    def test_price_settings_custom_values(self):
        """Test PriceSettings with custom values."""
        settings = PriceSettings(
            consumption=0.30,
            delivery=0.08,
            currency="EUR",
        )

        assert settings.consumption == pytest.approx(0.30)
        assert settings.delivery == pytest.approx(0.08)
        assert settings.currency == "EUR"

    def test_price_settings_is_configured_true_consumption_only(self):
        """Test is_configured when only consumption is set."""
        settings = PriceSettings(consumption=0.30, currency="EUR")

        assert settings.is_configured is True

    def test_price_settings_is_configured_true_delivery_only(self):
        """Test is_configured when only delivery is set."""
        settings = PriceSettings(delivery=0.08, currency="EUR")

        assert settings.is_configured is True

    def test_price_settings_is_configured_true_both(self):
        """Test is_configured when both prices are set."""
        settings = PriceSettings(
            consumption=0.30,
            delivery=0.08,
            currency="EUR",
        )

        assert settings.is_configured is True

    def test_price_settings_is_configured_false_no_currency(self):
        """Test is_configured returns False without currency."""
        settings = PriceSettings(consumption=0.30, delivery=0.08)

        assert settings.is_configured is False

    def test_price_settings_is_configured_false_no_prices(self):
        """Test is_configured returns False without prices."""
        settings = PriceSettings(currency="EUR")

        assert settings.is_configured is False

    def test_price_settings_is_consumption_configured(self):
        """Test is_consumption_configured property."""
        settings = PriceSettings(consumption=0.30, currency="EUR")

        assert settings.is_consumption_configured is True
        assert settings.is_delivery_configured is False

    def test_price_settings_is_delivery_configured(self):
        """Test is_delivery_configured property."""
        settings = PriceSettings(delivery=0.08, currency="EUR")

        assert settings.is_delivery_configured is True
        assert settings.is_consumption_configured is False

    def test_price_settings_price_in_with_consumption(self):
        """Test price_in returns consumption price."""
        settings = PriceSettings(consumption=0.30)

        assert settings.price_in == pytest.approx(0.30)

    def test_price_settings_price_in_without_consumption(self):
        """Test price_in returns 0.0 when consumption not set."""
        settings = PriceSettings()

        assert settings.price_in == pytest.approx(0.0)

    def test_price_settings_price_out_with_delivery(self):
        """Test price_out returns delivery price."""
        settings = PriceSettings(delivery=0.08)

        assert settings.price_out == pytest.approx(0.08)

    def test_price_settings_price_out_without_delivery(self):
        """Test price_out returns 0.0 when delivery not set."""
        settings = PriceSettings()

        assert settings.price_out == pytest.approx(0.0)


class TestPriceScheduleEntry:
    def test_defaults_cover_every_day_and_time(self):
        entry = PriceScheduleEntry(consumption=0.20)

        assert entry.months == []
        assert entry.weekdays == []
        assert entry.start_minute == 0
        assert entry.end_minute == 24 * 60
        assert not entry.wraps_midnight

    def test_normalizes_the_time_format(self):
        entry = PriceScheduleEntry(start="7:00", end="9:30")

        assert entry.start == "07:00"
        assert entry.end == "09:30"

    def test_accepts_unquoted_yaml_times(self):
        config = yaml.safe_load("start: 16:00\nend: 24:00")

        entry = PriceScheduleEntry(**config)

        assert entry.start == "16:00"
        assert entry.end == "24:00"

    def test_end_before_start_wraps_midnight(self):
        assert PriceScheduleEntry(start="22:00", end="06:00").wraps_midnight

    @pytest.mark.parametrize(
        "times",
        [
            {"start": "17:10"},
            {"end": "25:00"},
            {"start": "24:00"},
            {"start": "12:60"},
            {"end": "noon"},
        ],
    )
    def test_rejects_invalid_times(self, times):
        with pytest.raises(ValidationError):
            PriceScheduleEntry(**times)

    def test_rejects_invalid_months(self):
        with pytest.raises(ValidationError):
            PriceScheduleEntry(months=[0, 13])

    def test_rejects_invalid_weekdays(self):
        with pytest.raises(ValidationError):
            PriceScheduleEntry.model_validate({"weekdays": ["monday"]})


class TestPriceSettingsSchedule:
    def test_schedule_alone_configures_its_direction(self):
        settings = PriceSettings(
            currency="EUR", schedule=[PriceScheduleEntry(delivery=0.05)]
        )

        assert settings.is_delivery_configured
        assert not settings.is_consumption_configured
        assert settings.is_configured

    def test_schedule_without_currency_is_not_configured(self):
        settings = PriceSettings(schedule=[PriceScheduleEntry(consumption=0.20)])

        assert not settings.is_configured

    def test_entry_without_prices_configures_nothing(self):
        settings = PriceSettings(
            currency="EUR", schedule=[PriceScheduleEntry(start="17:00")]
        )

        assert not settings.is_configured

    def test_parses_a_schedule_from_mappings(self):
        settings = PriceSettings.model_validate(
            {
                "consumption": 0.30,
                "currency": "USD",
                "schedule": [
                    {
                        "name": "Summer peak",
                        "months": [6, 7, 8, 9],
                        "weekdays": ["mon", "tue", "wed", "thu", "fri"],
                        "start": "16:00",
                        "end": "21:00",
                        "consumption": 0.62,
                    }
                ],
            }
        )

        assert settings.schedule[0].name == "Summer peak"
        assert settings.schedule[0].consumption == pytest.approx(0.62)


class TestEnergySettings:
    """Tests for EnergySettings class."""

    def test_energy_settings_defaults(self):
        """Test EnergySettings default values."""
        settings = EnergySettings()

        assert settings.retain is False

    def test_energy_settings_custom_values(self):
        """Test EnergySettings with custom values."""
        settings = EnergySettings(retain=True)

        assert settings.retain is True
