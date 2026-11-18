from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from solaredge2mqtt.services.energy.prices import PriceResolver
from solaredge2mqtt.services.energy.settings import (
    PriceScheduleEntry,
    PriceSettings,
)


class TestPriceResolver:
    def test_returns_the_flat_prices_at_any_time(self):
        resolver = PriceResolver(
            PriceSettings(consumption=0.30, delivery=0.08, currency="EUR")
        )

        assert resolver.consumption_at(0) == pytest.approx(0.30)
        assert resolver.delivery_at(1_800_000_000) == pytest.approx(0.08)

    def test_unset_prices_resolve_to_zero(self):
        resolver = PriceResolver(PriceSettings())

        assert resolver.consumption_at(0) == pytest.approx(0.0)
        assert resolver.delivery_at(0) == pytest.approx(0.0)

    def test_is_configured_follows_the_settings(self):
        assert PriceResolver(
            PriceSettings(consumption=0.30, currency="EUR")
        ).is_configured
        assert not PriceResolver(PriceSettings(consumption=0.30)).is_configured


BERLIN = ZoneInfo("Europe/Berlin")


def at(*args) -> int:
    return int(datetime(*args, tzinfo=BERLIN).timestamp())


def resolver(
    *entries, consumption: float | None = 0.30, delivery: float | None = 0.08
) -> PriceResolver:
    return PriceResolver(
        PriceSettings(
            consumption=consumption,
            delivery=delivery,
            currency="EUR",
            schedule=[PriceScheduleEntry(**entry) for entry in entries],
        ),
        tz=BERLIN,
    )


class TestPriceSchedule:
    def test_entry_applies_inside_its_window(self):
        prices = resolver({"start": "17:00", "end": "21:00", "consumption": 0.50})

        assert prices.consumption_at(at(2026, 11, 18, 16, 45)) == pytest.approx(0.30)
        assert prices.consumption_at(at(2026, 11, 18, 17, 0)) == pytest.approx(0.50)
        assert prices.consumption_at(at(2026, 11, 18, 20, 45)) == pytest.approx(0.50)
        assert prices.consumption_at(at(2026, 11, 18, 21, 0)) == pytest.approx(0.30)

    def test_window_until_midnight(self):
        prices = resolver({"start": "22:00", "end": "24:00", "consumption": 0.20})

        assert prices.consumption_at(at(2026, 11, 18, 23, 45)) == pytest.approx(0.20)
        assert prices.consumption_at(at(2026, 11, 19, 0, 0)) == pytest.approx(0.30)

    def test_window_wraps_over_midnight(self):
        prices = resolver({"start": "22:00", "end": "06:00", "consumption": 0.20})

        assert prices.consumption_at(at(2026, 11, 18, 22, 0)) == pytest.approx(0.20)
        assert prices.consumption_at(at(2026, 11, 19, 5, 45)) == pytest.approx(0.20)
        assert prices.consumption_at(at(2026, 11, 19, 6, 0)) == pytest.approx(0.30)
        assert prices.consumption_at(at(2026, 11, 19, 12, 0)) == pytest.approx(0.30)

    def test_equal_start_and_end_cover_the_whole_day(self):
        prices = resolver({"start": "00:00", "end": "00:00", "consumption": 0.20})

        assert prices.consumption_at(at(2026, 11, 18, 0, 0)) == pytest.approx(0.20)
        assert prices.consumption_at(at(2026, 11, 18, 23, 45)) == pytest.approx(0.20)

    def test_weekdays_restrict_the_entry(self):
        prices = resolver({"weekdays": ["sat", "sun"], "consumption": 0.20})

        assert prices.consumption_at(at(2026, 11, 20, 12, 0)) == pytest.approx(0.30)
        assert prices.consumption_at(at(2026, 11, 21, 12, 0)) == pytest.approx(0.20)
        assert prices.consumption_at(at(2026, 11, 22, 12, 0)) == pytest.approx(0.20)

    def test_night_after_midnight_belongs_to_the_day_it_started(self):
        prices = resolver(
            {
                "weekdays": ["fri"],
                "start": "22:00",
                "end": "06:00",
                "consumption": 0.20,
            }
        )

        assert prices.consumption_at(at(2026, 11, 21, 2, 0)) == pytest.approx(0.20)
        assert prices.consumption_at(at(2026, 11, 20, 2, 0)) == pytest.approx(0.30)

    def test_months_restrict_the_entry(self):
        prices = resolver({"months": [6, 7, 8, 9], "consumption": 0.40})

        assert prices.consumption_at(at(2026, 7, 1, 12, 0)) == pytest.approx(0.40)
        assert prices.consumption_at(at(2026, 11, 1, 12, 0)) == pytest.approx(0.30)

    def test_first_matching_entry_wins(self):
        prices = resolver(
            {"start": "17:00", "end": "21:00", "consumption": 0.50},
            {"consumption": 0.25},
        )

        assert prices.consumption_at(at(2026, 11, 18, 18, 0)) == pytest.approx(0.50)
        assert prices.consumption_at(at(2026, 11, 18, 12, 0)) == pytest.approx(0.25)

    def test_entry_without_a_price_for_a_direction_is_skipped(self):
        prices = resolver(
            {"start": "17:00", "end": "21:00", "consumption": 0.50},
            {"start": "12:00", "end": "24:00", "delivery": 0.02},
        )

        assert prices.delivery_at(at(2026, 11, 18, 18, 0)) == pytest.approx(0.02)
        assert prices.consumption_at(at(2026, 11, 18, 13, 0)) == pytest.approx(0.30)

    def test_falls_back_to_zero_without_a_flat_price(self):
        prices = resolver(
            {"start": "17:00", "end": "21:00", "consumption": 0.50},
            consumption=None,
        )

        assert prices.is_configured
        assert prices.consumption_at(at(2026, 11, 18, 12, 0)) == pytest.approx(0.0)

    def test_uses_local_time_in_summer_and_winter(self):
        prices = resolver({"start": "17:00", "end": "21:00", "consumption": 0.50})
        summer = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)
        winter = datetime(2026, 11, 18, 16, 0, tzinfo=timezone.utc)

        assert prices.consumption_at(int(summer.timestamp())) == pytest.approx(0.50)
        assert prices.consumption_at(int(winter.timestamp())) == pytest.approx(0.50)

    def test_switch_to_summer_time_skips_the_missing_hour(self):
        prices = resolver({"start": "02:00", "end": "03:00", "consumption": 0.20})
        night = datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc)

        slots = [int((night + timedelta(minutes=15 * i)).timestamp()) for i in range(8)]

        assert [prices.consumption_at(slot) for slot in slots] == pytest.approx(
            [0.30] * 8
        )

    def test_switch_to_winter_time_applies_to_both_repeated_hours(self):
        prices = resolver({"start": "02:00", "end": "03:00", "consumption": 0.20})
        night = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)

        slots = [int((night + timedelta(minutes=15 * i)).timestamp()) for i in range(8)]

        assert [prices.consumption_at(slot) for slot in slots] == pytest.approx(
            [0.20] * 8
        )
