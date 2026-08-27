"""Tests for the ten minute aggregation job."""

from datetime import datetime, timedelta, timezone

import pytest

from solaredge2mqtt.core.storage.aggregation import aggregate
from solaredge2mqtt.core.storage.queries import EXCLUDED_POWER_FIELDS

NOW = datetime(2026, 8, 19, 12, 30, tzinfo=timezone.utc)
HOUR = datetime(2026, 8, 19, 11, 0, tzinfo=timezone.utc)


async def read(storage, measurement, field, tags=""):
    """Read the aggregated values of one series."""
    rows = await storage.fetch_all(
        "SELECT p.ts, p.value FROM point p JOIN series s ON s.series_id = p.series_id "
        "WHERE s.measurement = :measurement AND s.field = :field AND s.tags = :tags "
        "ORDER BY p.ts",
        {"measurement": measurement, "field": field, "tags": tags},
    )
    return [(row["ts"], row["value"]) for row in rows]


async def seed_constant_hour(seed, value=3600.0, field="pv_production", start=HOUR):
    """Seed a full hour of five second samples with a constant power."""
    samples = [
        (start + timedelta(seconds=offset), value) for offset in range(0, 3600, 5)
    ]
    await seed("powerflow_raw", field, {"unit": "cumulated"}, samples)


class TestPowerAggregates:
    """Tests for the hourly min, max and mean values."""

    @pytest.mark.asyncio
    async def test_writes_all_three_aggregation_types(self, storage, seed):
        """Every raw field becomes a min, a max and a mean series."""
        await seed(
            "powerflow_raw",
            "pv_production",
            {"unit": "cumulated"},
            [(HOUR, 100.0), (HOUR + timedelta(minutes=30), 300.0)],
        )

        await aggregate(storage, now=NOW)

        tags = "agg_type={},unit=cumulated"

        async def aggregated(agg_type):
            return await read(
                storage, "powerflow", "pv_production", tags.format(agg_type)
            )

        assert await aggregated("min") == [(int(HOUR.timestamp()), 100.0)]
        assert await aggregated("max") == [(int(HOUR.timestamp()), 300.0)]
        assert await aggregated("mean") == [(int(HOUR.timestamp()), 200.0)]

    @pytest.mark.asyncio
    async def test_excludes_the_derived_power_fields(self, storage, seed):
        """The combined power fields are derived, aggregating them is wrong."""
        for field in EXCLUDED_POWER_FIELDS:
            await seed("powerflow_raw", field, {}, [(HOUR, 100.0)])

        await aggregate(storage, now=NOW)

        rows = await storage.fetch_all(
            "SELECT COUNT(*) FROM series WHERE measurement = 'powerflow'"
        )

        assert rows[0][0] == 0

    @pytest.mark.asyncio
    async def test_aggregates_the_battery(self, storage, seed):
        """The battery is aggregated from its own raw measurement."""
        await seed(
            "battery_raw",
            "state_of_charge",
            {"unit": "1"},
            [(HOUR, 50.0), (HOUR + timedelta(minutes=30), 80.0)],
        )

        await aggregate(storage, now=NOW)

        assert await read(
            storage, "battery", "state_of_charge", "agg_type=mean,unit=1"
        ) == [(int(HOUR.timestamp()), 65.0)]

    @pytest.mark.asyncio
    async def test_buckets_are_stamped_at_the_hour_start(self, storage, seed):
        """The aggregate belongs to the hour it summarizes, not to its end."""
        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [(HOUR + timedelta(minutes=59), 100.0)],
        )

        await aggregate(storage, now=NOW)

        assert (await read(storage, "powerflow", "pv_production", "agg_type=min"))[0][
            0
        ] == int(HOUR.timestamp())


class TestEnergyAggregate:
    """Tests for the trapezoidal integration."""

    @pytest.mark.asyncio
    async def test_integrates_watts_into_kilowatt_hours(self, storage, seed):
        """A constant 3600 W hour is 3.6 kWh minus the trailing interval."""
        await seed_constant_hour(seed)

        await aggregate(storage, now=NOW)

        values = await read(storage, "energy", "pv_production", "unit=cumulated")

        assert values[0][1] == pytest.approx(3.595)

    @pytest.mark.asyncio
    async def test_trapezoid_of_a_ramp(self, storage, seed):
        """A ramp integrates to the mean of its ends over the sampled span."""
        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [(HOUR, 0.0), (HOUR + timedelta(minutes=30), 2000.0)],
        )

        await aggregate(storage, now=NOW)

        values = await read(storage, "energy", "pv_production")

        assert values[0][1] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_buckets_are_not_bridged(self, storage, seed):
        """Flux integrated inside each window, never across two of them."""
        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [
                (HOUR, 1000.0),
                (HOUR + timedelta(minutes=30), 1000.0),
                (HOUR + timedelta(hours=1), 1000.0),
            ],
        )

        await aggregate(storage, now=NOW)

        values = await read(storage, "energy", "pv_production")

        assert len(values) == 1
        assert values[0][0] == int(HOUR.timestamp())
        assert values[0][1] == pytest.approx(0.5)


class TestMoneyFields:
    """Tests for the price derived fields."""

    @pytest.mark.asyncio
    async def test_derives_savings_from_used_production(self, storage, seed):
        """Self consumed production is worth what it would have cost."""
        await seed_constant_hour(seed, field="consumer_used_production")

        await aggregate(storage, now=NOW)

        saved = await read(storage, "energy", "money_saved", "unit=cumulated")
        price = await read(storage, "energy", "money_price_in", "unit=cumulated")

        assert saved[0][1] == pytest.approx(3.595 * 0.30)
        assert price[0][1] == pytest.approx(0.30)

    @pytest.mark.asyncio
    async def test_derives_earnings_from_delivery(self, storage, seed):
        """Delivered energy is paid at the feed in price."""
        await seed_constant_hour(seed, field="grid_delivery")

        await aggregate(storage, now=NOW)

        delivered = await read(storage, "energy", "money_delivered", "unit=cumulated")
        price = await read(storage, "energy", "money_price_out", "unit=cumulated")

        assert delivered[0][1] == pytest.approx(3.595 * 0.08)
        assert price[0][1] == pytest.approx(0.08)

    @pytest.mark.asyncio
    async def test_derives_cost_from_consumption(self, storage, seed):
        """Grid consumption is billed at the consumption price."""
        await seed_constant_hour(seed, field="grid_consumption")

        await aggregate(storage, now=NOW)

        consumed = await read(storage, "energy", "money_consumed", "unit=cumulated")

        assert consumed[0][1] == pytest.approx(3.595 * 0.30)


class TestIdempotency:
    """Tests for repeatedly aggregating the same window."""

    @pytest.mark.asyncio
    async def test_rerunning_does_not_duplicate(self, storage, seed):
        """The job runs every ten minutes over the same two hours."""
        await seed_constant_hour(seed)

        await aggregate(storage, now=NOW)
        first = await storage.fetch_all("SELECT COUNT(*) FROM point")
        await aggregate(storage, now=NOW)
        second = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert first[0][0] == second[0][0]

    @pytest.mark.asyncio
    async def test_updates_the_running_hour(self, storage, seed):
        """The current partial hour is refined with every cycle."""
        current = NOW.replace(minute=0, second=0, microsecond=0)
        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [(current, 1000.0), (current + timedelta(minutes=10), 1000.0)],
        )
        await aggregate(storage, now=NOW)
        partial = (await read(storage, "energy", "pv_production"))[0][1]

        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [(current + timedelta(minutes=20), 1000.0)],
        )
        await aggregate(storage, now=NOW)
        refined = (await read(storage, "energy", "pv_production"))[0][1]

        assert refined > partial

    @pytest.mark.asyncio
    async def test_ignores_samples_before_the_window(self, storage, seed):
        """Only the last two hours plus the running one are reprocessed."""
        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [(HOUR - timedelta(days=1), 1000.0)],
        )

        assert await aggregate(storage, now=NOW) == []
