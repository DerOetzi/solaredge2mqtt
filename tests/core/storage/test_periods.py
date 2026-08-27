"""Tests for the calendar boundaries that replace the Flux time helpers."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from solaredge2mqtt.core.storage.periods import (
    LIFETIME_START,
    LIFETIME_STOP,
    as_epoch,
    day_bounds,
    from_epoch,
    hour_start,
    local_zone,
    period_bounds,
)
from solaredge2mqtt.services.energy.models import HistoricPeriod

BERLIN = ZoneInfo("Europe/Berlin")
AUCKLAND = ZoneInfo("Pacific/Auckland")

NOW = datetime(2026, 8, 19, 14, 30, tzinfo=timezone.utc)


def bounds(period, now=NOW, tz=BERLIN):
    """Return the local boundaries of a period as naive wall clock values."""
    start, stop = period_bounds(period, now, tz)
    return start.replace(tzinfo=None), stop.replace(tzinfo=None)


class TestHourBoundaries:
    """Tests for the hourly periods."""

    def test_last_hour_is_the_previous_full_hour(self):
        """The last hour ends where the current one begins."""
        start, stop = bounds(HistoricPeriod.LAST_HOUR)

        assert (start.hour, stop.hour) == (15, 16)

    def test_hour_start_truncates_in_utc(self):
        """The aggregation buckets are UTC hours, like the Flux windows were."""
        assert hour_start(NOW) == datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)


class TestDayBoundaries:
    """Tests for the daily periods."""

    def test_today_starts_at_local_midnight(self):
        """Today is a local day, not a UTC day."""
        start, stop = bounds(HistoricPeriod.TODAY)

        assert start == datetime(2026, 8, 19, 0, 0)
        assert stop == datetime(2026, 8, 20, 0, 0)

    def test_yesterday_precedes_today(self):
        """Yesterday ends exactly where today starts."""
        start, stop = bounds(HistoricPeriod.YESTERDAY)

        assert start == datetime(2026, 8, 18, 0, 0)
        assert stop == datetime(2026, 8, 19, 0, 0)

    def test_spring_forward_day_is_23_hours(self):
        """Adding a timedelta instead of a calendar day would be an hour off."""
        now = datetime(2025, 3, 30, 12, 0, tzinfo=timezone.utc)
        start, stop = period_bounds(HistoricPeriod.TODAY, now, BERLIN)

        assert as_epoch(stop) - as_epoch(start) == 23 * 3600

    def test_fall_back_day_is_25_hours(self):
        """The same holds for the long day in autumn."""
        now = datetime(2025, 10, 26, 12, 0, tzinfo=timezone.utc)
        start, stop = period_bounds(HistoricPeriod.TODAY, now, BERLIN)

        assert as_epoch(stop) - as_epoch(start) == 25 * 3600

    def test_southern_hemisphere_transition(self):
        """The rules come from the zone, not from a hardcoded hemisphere."""
        now = datetime(2025, 9, 28, 0, 0, tzinfo=timezone.utc)
        start, stop = period_bounds(HistoricPeriod.TODAY, now, AUCKLAND)

        assert as_epoch(stop) - as_epoch(start) == 23 * 3600


class TestWeekBoundaries:
    """Tests for the weekly periods."""

    def test_week_starts_on_monday(self):
        """Flux weeks start on Monday, the sensors must not shift by a day."""
        start, stop = bounds(HistoricPeriod.THIS_WEEK)

        assert start == datetime(2026, 8, 17, 0, 0)
        assert stop == datetime(2026, 8, 24, 0, 0)

    def test_last_week_precedes_this_week(self):
        """The previous week ends where the current one starts."""
        start, stop = bounds(HistoricPeriod.LAST_WEEK)

        assert start == datetime(2026, 8, 10, 0, 0)
        assert stop == datetime(2026, 8, 17, 0, 0)

    def test_week_of_a_monday_starts_that_day(self):
        """On a Monday the current week starts the same day."""
        monday = datetime(2026, 8, 17, 10, 0, tzinfo=timezone.utc)
        start, _ = bounds(HistoricPeriod.THIS_WEEK, now=monday)

        assert start == datetime(2026, 8, 17, 0, 0)


class TestMonthBoundaries:
    """Tests for the monthly periods."""

    def test_this_month(self):
        """The current month runs to the first of the next one."""
        start, stop = bounds(HistoricPeriod.THIS_MONTH)

        assert start == datetime(2026, 8, 1, 0, 0)
        assert stop == datetime(2026, 9, 1, 0, 0)

    def test_last_month(self):
        """The previous month ends where the current one starts."""
        start, stop = bounds(HistoricPeriod.LAST_MONTH)

        assert start == datetime(2026, 7, 1, 0, 0)
        assert stop == datetime(2026, 8, 1, 0, 0)

    def test_january_rolls_back_into_december(self):
        """The month arithmetic has to cross the year boundary."""
        now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        start, stop = bounds(HistoricPeriod.LAST_MONTH, now=now)

        assert start == datetime(2025, 12, 1, 0, 0)
        assert stop == datetime(2026, 1, 1, 0, 0)

    def test_december_rolls_forward_into_january(self):
        """And in the other direction as well."""
        now = datetime(2026, 12, 15, 12, 0, tzinfo=timezone.utc)
        _, stop = bounds(HistoricPeriod.THIS_MONTH, now=now)

        assert stop == datetime(2027, 1, 1, 0, 0)

    def test_february_of_a_leap_year(self):
        """A short month must not produce an invalid day."""
        now = datetime(2024, 2, 29, 12, 0, tzinfo=timezone.utc)
        start, stop = bounds(HistoricPeriod.THIS_MONTH, now=now)

        assert start == datetime(2024, 2, 1, 0, 0)
        assert stop == datetime(2024, 3, 1, 0, 0)


class TestYearBoundaries:
    """Tests for the yearly periods."""

    def test_this_year(self):
        """The current year runs to the first of January."""
        start, stop = bounds(HistoricPeriod.THIS_YEAR)

        assert start == datetime(2026, 1, 1, 0, 0)
        assert stop == datetime(2027, 1, 1, 0, 0)

    def test_last_year(self):
        """The previous year ends where the current one starts."""
        start, stop = bounds(HistoricPeriod.LAST_YEAR)

        assert start == datetime(2025, 1, 1, 0, 0)
        assert stop == datetime(2026, 1, 1, 0, 0)


class TestLifetime:
    """Tests for the open ended period."""

    def test_lifetime_spans_everything(self):
        """Lifetime is not a calendar period, it covers the whole database."""
        start, stop = period_bounds(HistoricPeriod.LIFETIME, NOW, BERLIN)

        assert (start, stop) == (LIFETIME_START, LIFETIME_STOP)


class TestHelpers:
    """Tests for the conversion helpers."""

    def test_day_bounds_span_the_requested_days(self):
        """publish_forecast asks for today plus the following day."""
        start, stop = day_bounds(NOW, BERLIN, days=2)

        assert start.replace(tzinfo=None) == datetime(2026, 8, 19, 0, 0)
        assert stop.replace(tzinfo=None) == datetime(2026, 8, 21, 0, 0)

    def test_epoch_round_trip(self):
        """Timestamps survive the trip through the database as UTC."""
        assert from_epoch(as_epoch(NOW)) == NOW

    def test_local_zone_resolves_a_name(self):
        """The service zone comes from tzlocal as a name."""
        assert local_zone("Europe/Berlin") == BERLIN

    def test_unsupported_unit_raises(self):
        """A new period unit must not silently fall back to a wrong range."""
        period = MagicMock()
        period.unit = "1q"
        period.query = HistoricPeriod.TODAY.query

        with pytest.raises(ValueError):
            period_bounds(period, NOW, BERLIN)
