"""Tests for the raw and long term retention."""

from datetime import datetime, timedelta, timezone

import pytest

from solaredge2mqtt.core.storage.retention import (
    LAST_RETENTION_RUN_KEY,
    apply_raw_retention,
    maybe_apply_long_retention,
    run_maintenance,
)
from solaredge2mqtt.core.storage.settings import StorageSettings

NOW = datetime(2026, 8, 19, 12, 30, tzinfo=timezone.utc)


async def count_points(storage):
    """Count every stored point."""
    rows = await storage.fetch_all("SELECT COUNT(*) FROM point")
    return rows[0][0]


class TestRawRetention:
    """Tests for dropping the five second samples."""

    @pytest.mark.asyncio
    async def test_removes_samples_older_than_the_window(self, storage, seed):
        """Raw data is kept for a day, the aggregates carry the history."""
        old = NOW - timedelta(hours=30)
        await seed("powerflow_raw", "pv_production", {}, [(old, 1.0)])

        assert await apply_raw_retention(storage, now=NOW) == 1
        assert await count_points(storage) == 0

    @pytest.mark.asyncio
    async def test_keeps_samples_inside_the_window(self, storage, seed):
        """Everything within retention_raw hours has to survive."""
        recent = NOW - timedelta(hours=2)
        await seed("battery_raw", "state_of_charge", {}, [(recent, 50.0)])

        assert await apply_raw_retention(storage, now=NOW) == 0
        assert await count_points(storage) == 1

    @pytest.mark.asyncio
    async def test_leaves_aggregates_untouched(self, storage, seed):
        """Only the raw measurements are subject to the short window."""
        old = NOW - timedelta(days=400)
        await seed("energy", "pv_production", {}, [(old, 1.0)])

        await apply_raw_retention(storage, now=NOW)

        assert await count_points(storage) == 1


class TestLongRetention:
    """Tests for the optional history limit."""

    @pytest.mark.asyncio
    async def test_disabled_by_default(self, storage, seed):
        """Locally there is no reason to discard hourly history."""
        await seed("energy", "pv_production", {}, [(NOW - timedelta(days=400), 1.0)])

        assert await maybe_apply_long_retention(storage, now=NOW) == 0
        assert await count_points(storage) == 1

    @pytest.mark.asyncio
    async def test_removes_data_beyond_the_retention(self, tmp_path, prices):
        """A configured retention drops everything older than its window."""
        from solaredge2mqtt.core.storage import Point, StorageService

        settings = StorageSettings(retention=86400)
        service = StorageService(settings, prices, config_dir=str(tmp_path))
        await service.async_init()

        try:
            old = Point("energy").time(NOW - timedelta(days=10)).field("pv", 1.0)
            recent = Point("energy").time(NOW).field("pv", 2.0)
            await service.write_points([old, recent])

            assert await maybe_apply_long_retention(service, now=NOW) == 1
            assert await count_points(service) == 1
        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_runs_at_most_once_a_day(self, tmp_path, prices):
        """The cycle fires every ten minutes, the retention pass must not."""
        from solaredge2mqtt.core.storage import StorageService

        settings = StorageSettings(retention=86400)
        service = StorageService(settings, prices, config_dir=str(tmp_path))
        await service.async_init()

        try:
            await maybe_apply_long_retention(service, now=NOW)
            stamp = await service.read_meta(LAST_RETENTION_RUN_KEY)

            assert stamp == str(int(NOW.timestamp()))
            assert (
                await maybe_apply_long_retention(
                    service, now=NOW + timedelta(minutes=10)
                )
                == 0
            )
        finally:
            await service.close()

    @pytest.mark.asyncio
    async def test_runs_again_the_next_day(self, tmp_path, prices):
        """After a day the pass is due again."""
        from solaredge2mqtt.core.storage import Point, StorageService

        settings = StorageSettings(retention=86400)
        service = StorageService(settings, prices, config_dir=str(tmp_path))
        await service.async_init()

        try:
            await maybe_apply_long_retention(service, now=NOW)
            later = NOW + timedelta(days=2)
            await service.write_points(
                [Point("energy").time(NOW - timedelta(days=5)).field("pv", 1.0)]
            )

            assert await maybe_apply_long_retention(service, now=later) == 1
        finally:
            await service.close()


class TestMaintenance:
    """Tests for the housekeeping pragmas."""

    @pytest.mark.asyncio
    async def test_maintenance_keeps_the_database_usable(self, storage, seed):
        """Vacuum and checkpoint must not disturb the open connections."""
        await seed("energy", "pv_production", {}, [(NOW, 1.0)])

        await run_maintenance(storage)

        assert await count_points(storage) == 1
