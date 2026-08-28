"""Tests for the storage gateway write and read paths."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from solaredge2mqtt.core.storage import Point
from solaredge2mqtt.core.storage.events import (
    StorageAggregatedEvent,
    StorageOfflineEvent,
    StorageOnlineEvent,
)
from solaredge2mqtt.services.energy.models import HistoricPeriod


class TestWritePath:
    """Tests for writing points."""

    @pytest.mark.asyncio
    async def test_round_trip(self, storage, hour, seed):
        """A written field comes back with its measurement, tags and value."""
        await seed("powerflow_raw", "pv_production", {"unit": "a"}, [(hour, 5)])

        rows = await storage.fetch_all(
            "SELECT s.measurement, s.field, s.tags, p.ts, p.value FROM point p "
            "JOIN series s ON s.series_id = p.series_id"
        )

        assert len(rows) == 1
        assert rows[0]["measurement"] == "powerflow_raw"
        assert rows[0]["field"] == "pv_production"
        assert rows[0]["tags"] == "unit=a"
        assert rows[0]["value"] == 5

    @pytest.mark.asyncio
    async def test_same_series_and_timestamp_overwrites(self, storage, hour, seed):
        """The idempotent re-aggregation depends on this upsert behaviour."""
        await seed("energy", "pv_production", {}, [(hour, 1.0)])
        await seed("energy", "pv_production", {}, [(hour, 2.0)])

        rows = await storage.fetch_all("SELECT value FROM point")

        assert [row["value"] for row in rows] == [2.0]

    @pytest.mark.asyncio
    async def test_stores_string_fields(self, storage, hour):
        """forecast_training carries weather_main, a string next to floats."""
        point = Point("forecast_training").time(hour)
        point.field("weather_main", "Clouds").field("energy", 1.5)
        await storage.write_points([point])

        rows = await storage.fetch_all(
            "SELECT s.field, p.value FROM point p "
            "JOIN series s ON s.series_id = p.series_id ORDER BY s.field"
        )

        assert [(row["field"], row["value"]) for row in rows] == [
            ("energy", 1.5),
            ("weather_main", "Clouds"),
        ]

    @pytest.mark.asyncio
    async def test_creates_series_tags(self, storage, hour, seed):
        """Tags are stored per series so queries can filter and group on them."""
        await seed(
            "modules",
            "power",
            {"serialnumber": "SN1", "name": "Module 1"},
            [(hour, 250.0)],
        )

        rows = await storage.fetch_all(
            "SELECT tag_key, tag_value FROM series_tag ORDER BY tag_key"
        )

        assert [(row["tag_key"], row["tag_value"]) for row in rows] == [
            ("name", "Module 1"),
            ("serialnumber", "SN1"),
        ]

    @pytest.mark.asyncio
    async def test_series_are_cached(self, storage, hour, seed):
        """The hot write path resolves a series once, not on every sample."""
        await seed("powerflow_raw", "pv_production", {}, [(hour, 1.0)])
        cached = dict(storage._series_cache)

        await seed(
            "powerflow_raw",
            "pv_production",
            {},
            [(hour + timedelta(seconds=5), 2.0)],
        )

        assert storage._series_cache == cached

    @pytest.mark.asyncio
    async def test_write_point_delegates(self, storage, hour):
        """A single point takes the same path as a batch."""
        await storage.write_point(Point("energy").time(hour).field("pv_production", 1))

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert rows[0][0] == 1

    @pytest.mark.asyncio
    async def test_unresolvable_series_raises(self, storage, hour):
        """A row that neither inserts nor selects must not write a null series."""
        with patch(
            "solaredge2mqtt.core.storage.SELECT_SERIES",
            "SELECT series_id FROM series WHERE 0 = ? AND 0 = ? AND 0 = ?",
        ):
            with pytest.raises(RuntimeError, match="Could not resolve series"):
                await storage.write_point(
                    Point("energy").time(hour).field("pv_production", 1)
                )

    @pytest.mark.asyncio
    async def test_empty_batch_is_a_no_op(self, storage):
        """An empty read cycle must not open a transaction."""
        await storage.write_points([])

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert rows[0][0] == 0


class TestStatusEvents:
    """Tests for the online and offline status reporting."""

    @pytest.mark.asyncio
    async def test_write_emits_online(self, storage, mock_event_bus, hour, seed):
        """A successful write proves the storage is reachable."""
        await seed("energy", "pv_production", {}, [(hour, 1.0)])

        assert isinstance(mock_event_bus.emit.call_args[0][0], StorageOnlineEvent)

    @pytest.mark.asyncio
    async def test_failed_write_emits_offline_and_reraises(
        self, storage, mock_event_bus, hour, seed
    ):
        """A broken database has to surface as an offline status."""
        with patch.object(
            storage.write_connection, "executemany", side_effect=RuntimeError("broken")
        ):
            with pytest.raises(RuntimeError):
                await seed("energy", "pv_production", {}, [(hour, 1.0)])

        assert isinstance(mock_event_bus.emit.call_args[0][0], StorageOfflineEvent)

    @pytest.mark.asyncio
    async def test_failed_execute_write_emits_offline_and_reraises(
        self, storage, mock_event_bus
    ):
        """Retention and consolidation write through execute_write."""
        with pytest.raises(Exception):
            await storage.execute_write("DELETE FROM does_not_exist")

        assert isinstance(mock_event_bus.emit.call_args[0][0], StorageOfflineEvent)

    @pytest.mark.asyncio
    async def test_failed_read_emits_offline_and_reraises(
        self, storage, mock_event_bus
    ):
        """A failing query reports offline just like a failing write."""
        with pytest.raises(Exception):
            await storage.fetch_all("SELECT * FROM does_not_exist")

        assert isinstance(mock_event_bus.emit.call_args[0][0], StorageOfflineEvent)

    @pytest.mark.asyncio
    async def test_set_online_carries_debounce_cycles(self, storage, mock_event_bus):
        """The status controller learns the debounce configuration from us."""
        await storage.set_online()

        event = mock_event_bus.emit.call_args[0][0]

        assert event.debounce_cycles == storage.settings.debounce_cycles

    @pytest.mark.asyncio
    async def test_close_emits_offline(self, tmp_path, storage_settings, prices):
        """Shutting down publishes an offline status before the file closes."""
        from solaredge2mqtt.core.storage import StorageService

        service = StorageService(storage_settings, prices, config_dir=str(tmp_path))
        await service.async_init()

        with patch(
            "solaredge2mqtt.core.events.EventBus.emit", new_callable=AsyncMock
        ) as emit:
            await service.close()

        assert isinstance(emit.call_args[0][0], StorageOfflineEvent)


class TestUninitialized:
    """Tests for using the gateway before async_init."""

    def test_write_connection_raises(self, storage_settings, prices):
        """Using the gateway before initialization is a programming error."""
        from solaredge2mqtt.core.storage import StorageService

        service = StorageService(storage_settings, prices, config_dir="config")

        with pytest.raises(RuntimeError):
            _ = service.write_connection

    def test_read_connection_raises(self, storage_settings, prices):
        """The read connection is created together with the write connection."""
        from solaredge2mqtt.core.storage import StorageService

        service = StorageService(storage_settings, prices, config_dir="config")

        with pytest.raises(RuntimeError):
            _ = service.read_connection

    @pytest.mark.asyncio
    async def test_close_without_connections_is_a_no_op(self, storage_settings, prices):
        """A failed startup still runs the shutdown path of the service."""
        from solaredge2mqtt.core.storage import StorageService

        service = StorageService(storage_settings, prices, config_dir="config")

        await service.close()


class TestMeta:
    """Tests for the key value side table."""

    @pytest.mark.asyncio
    async def test_missing_key_returns_none(self, storage):
        """An unknown key reads as absent, not as an empty string."""
        assert await storage.read_meta("missing") is None

    @pytest.mark.asyncio
    async def test_write_and_overwrite(self, storage):
        """Writing the same key twice keeps the latest value."""
        await storage.write_meta("cursor", "1")
        await storage.write_meta("cursor", "2")

        assert await storage.read_meta("cursor") == "2"


class TestQueryTimeunit:
    """Tests for the period sums that feed the historic energy sensors."""

    @pytest.mark.asyncio
    async def test_returns_none_without_data(self, storage):
        """An empty period is reported as missing, not as a zero record."""
        assert await storage.query_timeunit(HistoricPeriod.LAST_HOUR, "energy") is None

    @pytest.mark.asyncio
    async def test_sums_fields_of_the_period(self, storage, hour, seed):
        """The record holds the summed fields plus the range boundaries."""
        now = datetime.now(tz=timezone.utc)
        hour = now.replace(minute=0, second=0, microsecond=0)
        await seed(
            "energy",
            "pv_production",
            {},
            [(hour, 1.0), (hour + timedelta(minutes=30), 2.0)],
        )

        records = await storage.query_timeunit(HistoricPeriod.TODAY, "energy")

        assert records is not None
        assert records[0]["pv_production"] == 3.0
        assert records[0]["_start"] < records[0]["_stop"]

    @pytest.mark.asyncio
    async def test_untagged_records_omit_the_unit_key(self, storage, seed):
        """HistoricInfo distinguishes a missing unit from an empty one."""
        now = datetime.now(tz=timezone.utc)
        await seed("energy", "pv_production", {}, [(now, 1.0)])

        records = await storage.query_timeunit(HistoricPeriod.TODAY, "energy")

        assert records is not None
        assert "unit" not in records[0]

    @pytest.mark.asyncio
    async def test_all_fields_of_a_unit_share_one_record(self, storage, seed):
        """The second field of a unit joins the record the first one opened."""
        now = datetime.now(tz=timezone.utc)
        await seed("energy", "pv_production", {"unit": "a"}, [(now, 1.0)])
        await seed("energy", "grid_consumption", {"unit": "a"}, [(now, 2.0)])

        records = await storage.query_timeunit(HistoricPeriod.TODAY, "energy")

        assert records is not None
        assert len(records) == 1
        assert records[0]["pv_production"] == 1.0
        assert records[0]["grid_consumption"] == 2.0

    @pytest.mark.asyncio
    async def test_tagged_records_carry_the_unit(self, storage, seed):
        """One record per unit, each stamped with the unit it belongs to."""
        now = datetime.now(tz=timezone.utc)
        await seed("energy", "pv_production", {"unit": "a"}, [(now, 1.0)])
        await seed("energy", "pv_production", {"unit": "b"}, [(now, 2.0)])

        records = await storage.query_timeunit(HistoricPeriod.TODAY, "energy")

        assert records is not None
        assert {record["unit"] for record in records} == {"a", "b"}


class TestQueryPivot:
    """Tests for the wide record lists consumed by the forecast service."""

    @pytest.mark.asyncio
    async def test_folds_fields_of_one_timestamp(self, storage, hour):
        """Every timestamp becomes a single record of all its fields."""
        point = Point("forecast_training").time(hour)
        point.field("energy", 1.5).field("power", 1500)
        await storage.write_points([point])

        records = await storage.query_pivot("forecast_training", 0)

        assert records == [{"_time": hour, "energy": 1.5, "power": 1500}]

    @pytest.mark.asyncio
    async def test_missing_fields_are_absent(self, storage, hour, seed):
        """Older rows simply lack the newer keys, the frame fills them in."""
        await seed("forecast", "energy", {}, [(hour, 1.0)])
        later = hour + timedelta(hours=1)
        point = Point("forecast").time(later).field("energy", 2.0).field("power", 2000)
        await storage.write_points([point])

        records = await storage.query_pivot("forecast", 0)

        assert "power" not in records[0]
        assert records[1]["power"] == 2000

    @pytest.mark.asyncio
    async def test_stop_bound_is_exclusive(self, storage, hour, seed):
        """The upper bound must not include the first row of the next range."""
        later = hour + timedelta(hours=1)
        await seed("forecast", "energy", {}, [(hour, 1.0), (later, 2.0)])

        records = await storage.query_pivot(
            "forecast", int(hour.timestamp()), int(later.timestamp())
        )

        assert len(records) == 1

    @pytest.mark.asyncio
    async def test_query_days_covers_the_local_days(self, storage, seed):
        """publish_forecast reads today plus the following day."""
        now = datetime.now(tz=timezone.utc)
        await seed("forecast", "energy", {}, [(now, 1.0)])

        records = await storage.query_days("forecast", 2, now=now)

        assert len(records) == 1


class TestQueryProductionLastHour:
    """Tests for the training label of the previous hour."""

    @pytest.mark.asyncio
    async def test_returns_none_without_samples(self, storage, hour):
        """Without samples the forecast service raises on missing production."""
        assert await storage.query_production_last_hour(now=hour) is None

    @pytest.mark.asyncio
    async def test_returns_none_with_a_single_sample(self, storage, hour, seed):
        """One sample spans no interval, so there is nothing to integrate."""
        previous = hour - timedelta(hours=1)
        await seed("powerflow_raw", "pv_production", {}, [(previous, 100.0)])

        assert await storage.query_production_last_hour(now=hour) is None

    @pytest.mark.asyncio
    async def test_integrates_the_previous_hour(self, storage, hour, seed):
        """A constant 3600 W over the hour is 3600 Wh minus the last interval."""
        previous = hour - timedelta(hours=1)
        samples = [
            (previous + timedelta(seconds=offset), 3600.0)
            for offset in range(0, 3600, 5)
        ]
        await seed("powerflow_raw", "pv_production", {}, samples)

        result = await storage.query_production_last_hour(now=hour)

        assert result is not None
        assert result["energy"] == pytest.approx(3595.0)
        assert result["power"] == pytest.approx(3600.0)
        assert result["_time"] == previous

    @pytest.mark.asyncio
    async def test_ignores_other_units(self, storage, hour, seed):
        """Only the cumulated series is a plant total, per unit values are not."""
        previous = hour - timedelta(hours=1)
        samples = [
            (previous + timedelta(seconds=offset), 3600.0) for offset in (0, 1800)
        ]
        await seed("powerflow_raw", "pv_production", {"unit": "leader"}, samples)

        assert await storage.query_production_last_hour(now=hour) is None


class TestLoop:
    """Tests for the ten minute maintenance cycle."""

    @pytest.mark.asyncio
    async def test_aggregates_then_emits(self, storage, mock_event_bus):
        """The energy service reads only after the aggregates are written."""
        await storage.loop(None)

        assert isinstance(mock_event_bus.emit.call_args[0][0], StorageAggregatedEvent)
