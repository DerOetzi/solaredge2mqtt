"""Tests for core InfluxDBAsync module with mocking."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.influxdb import InfluxDBAsync
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent
from solaredge2mqtt.core.influxdb.settings import InfluxDBSettings
from solaredge2mqtt.services.energy.settings import PriceSettings


@pytest.fixture
def influxdb_settings():
    """Create InfluxDBSettings for testing."""
    return InfluxDBSettings(
        host="localhost",
        port=8086,
        token="test_token",
        org="test_org",
        bucket="test_bucket",
        retention=2592000,  # 30 days in seconds
        retention_raw=24,  # 24 hours
    )


@pytest.fixture
def price_settings():
    """Create PriceSettings for testing."""
    return PriceSettings(
        consumption=0.30,
        delivery=0.08,
        currency="EUR",
    )


@pytest.fixture
def mock_influxdb_client():
    """Create mock InfluxDB clients."""
    with patch("solaredge2mqtt.core.influxdb.InfluxDBClient") as mock_sync, patch(
        "solaredge2mqtt.core.influxdb.InfluxDBClientAsync"
    ) as mock_async:
        mock_sync_instance = MagicMock()
        mock_sync.return_value = mock_sync_instance

        mock_async_instance = AsyncMock()
        mock_async.return_value = mock_async_instance

        yield mock_sync_instance, mock_async_instance


class TestInfluxDBAsyncInit:
    """Tests for InfluxDBAsync initialization."""

    def test_influxdb_async_init_without_event_bus(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test InfluxDBAsync initialization without event bus."""
        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        assert influxdb.settings == influxdb_settings
        assert influxdb.prices == price_settings
        assert influxdb.event_bus is None
        assert influxdb.client_async is None

    def test_influxdb_async_init_with_event_bus(
        self, influxdb_settings, price_settings, mock_event_bus, mock_influxdb_client
    ):
        """Test InfluxDBAsync initialization with event bus."""
        influxdb = InfluxDBAsync(influxdb_settings, price_settings, mock_event_bus)

        assert influxdb.event_bus is mock_event_bus
        # Verify it subscribed to the 10min trigger event
        mock_event_bus.subscribe.assert_called()

    def test_influxdb_async_bucket_name(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test bucket_name property."""
        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        assert influxdb.bucket_name == "test_bucket"


class TestInfluxDBAsyncInitialize:
    """Tests for InfluxDBAsync initialize methods."""

    def test_init_method(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test init method creates async client and initializes buckets."""
        mock_sync, mock_async = mock_influxdb_client

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        # Mock buckets_api
        mock_buckets_api = MagicMock()
        mock_buckets_api.find_bucket_by_name.return_value = None
        mock_sync.buckets_api.return_value = mock_buckets_api

        influxdb.init()

        # Async client should be created
        assert influxdb.client_async is not None

    def test_initialize_buckets_creates_new(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test initialize_buckets creates bucket when it doesn't exist."""
        mock_sync, mock_async = mock_influxdb_client

        mock_buckets_api = MagicMock()
        mock_buckets_api.find_bucket_by_name.return_value = None
        mock_sync.buckets_api.return_value = mock_buckets_api

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.initialize_buckets()

        mock_buckets_api.create_bucket.assert_called_once()

    def test_initialize_buckets_updates_existing(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test initialize_buckets updates bucket with different retention."""
        mock_sync, mock_async = mock_influxdb_client

        # Mock existing bucket with different retention
        mock_bucket = MagicMock()
        mock_retention_rule = MagicMock()
        mock_retention_rule.every_seconds = 999999  # Different from settings
        mock_bucket.retention_rules = [mock_retention_rule]

        mock_buckets_api = MagicMock()
        mock_buckets_api.find_bucket_by_name.return_value = mock_bucket
        mock_sync.buckets_api.return_value = mock_buckets_api

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.initialize_buckets()

        mock_buckets_api.update_bucket.assert_called_once()

    def test_initialize_buckets_no_update_same_retention(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test initialize_buckets doesn't update bucket with same retention."""
        mock_sync, mock_async = mock_influxdb_client

        # Mock existing bucket with same retention
        mock_bucket = MagicMock()
        mock_retention_rule = MagicMock()
        mock_retention_rule.every_seconds = 2592000  # Same as settings
        mock_bucket.retention_rules = [mock_retention_rule]

        mock_buckets_api = MagicMock()
        mock_buckets_api.find_bucket_by_name.return_value = mock_bucket
        mock_sync.buckets_api.return_value = mock_buckets_api

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.initialize_buckets()

        mock_buckets_api.update_bucket.assert_not_called()


class TestInfluxDBAsyncWrite:
    """Tests for InfluxDBAsync write methods."""

    @pytest.mark.asyncio
    async def test_write_point(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test write_point writes single point."""
        mock_sync, mock_async = mock_influxdb_client

        mock_write_api = MagicMock()
        mock_write_api.write = AsyncMock()
        # write_api() is a regular method that returns the api object
        mock_async.write_api = MagicMock(return_value=mock_write_api)

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = mock_async

        mock_point = MagicMock()
        await influxdb.write_point(mock_point)

        mock_write_api.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_write_points(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test write_points writes multiple points."""
        mock_sync, mock_async = mock_influxdb_client

        mock_write_api = MagicMock()
        mock_write_api.write = AsyncMock()
        mock_async.write_api = MagicMock(return_value=mock_write_api)

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = mock_async

        mock_points = [MagicMock(), MagicMock()]
        await influxdb.write_points(mock_points)

        mock_write_api.write.assert_called_once_with(
            bucket="test_bucket", record=mock_points
        )


class TestInfluxDBAsyncQuery:
    """Tests for InfluxDBAsync query methods."""

    @pytest.mark.asyncio
    async def test_query_returns_records(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test query returns records from tables."""
        mock_sync, mock_async = mock_influxdb_client

        # Mock query result
        mock_record = MagicMock()
        mock_record.values = {"field": "value"}
        mock_table = MagicMock()
        mock_table.records = [mock_record]

        mock_query_api = MagicMock()
        mock_query_api.query = AsyncMock(return_value=[mock_table])
        # query_api() is a regular method that returns the api object
        mock_async.query_api = MagicMock(return_value=mock_query_api)

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = mock_async

        # Cache a test query
        influxdb.flux_cache["test_query"] = "test flux query"

        result = await influxdb.query("test_query")

        assert len(result) == 1
        assert result[0]["field"] == "value"

    @pytest.mark.asyncio
    async def test_query_first_returns_first_record(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test query_first returns first record."""
        mock_sync, mock_async = mock_influxdb_client

        mock_record1 = MagicMock()
        mock_record1.values = {"field": "first"}
        mock_record2 = MagicMock()
        mock_record2.values = {"field": "second"}
        mock_table = MagicMock()
        mock_table.records = [mock_record1, mock_record2]

        mock_query_api = MagicMock()
        mock_query_api.query = AsyncMock(return_value=[mock_table])
        mock_async.query_api = MagicMock(return_value=mock_query_api)

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = mock_async
        influxdb.flux_cache["test_query"] = "test flux query"

        result = await influxdb.query_first("test_query")

        assert result["field"] == "first"

    @pytest.mark.asyncio
    async def test_query_first_returns_none_when_empty(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test query_first returns None when no records."""
        mock_sync, mock_async = mock_influxdb_client

        mock_query_api = MagicMock()
        mock_query_api.query = AsyncMock(return_value=[])
        mock_async.query_api = MagicMock(return_value=mock_query_api)

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = mock_async
        influxdb.flux_cache["test_query"] = "test flux query"

        result = await influxdb.query_first("test_query")

        assert result is None


class TestInfluxDBAsyncDelete:
    """Tests for InfluxDBAsync delete methods."""

    def test_delete_from_measurement(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test delete_from_measurement."""
        mock_sync, mock_async = mock_influxdb_client

        mock_delete_api = MagicMock()
        mock_sync.delete_api.return_value = mock_delete_api

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        stop = datetime(2024, 1, 2, tzinfo=timezone.utc)

        influxdb.delete_from_measurement(start, stop, "test_measurement")

        mock_delete_api.delete.assert_called_once_with(
            start, stop, '_measurement="test_measurement"', "test_bucket"
        )

    def test_delete_from_measurements(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test delete_from_measurements."""
        mock_sync, mock_async = mock_influxdb_client

        mock_delete_api = MagicMock()
        mock_sync.delete_api.return_value = mock_delete_api

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        stop = datetime(2024, 1, 2, tzinfo=timezone.utc)

        influxdb.delete_from_measurements(start, stop, ["m1", "m2"])

        assert mock_delete_api.delete.call_count == 2


class TestInfluxDBAsyncLoop:
    """Tests for InfluxDBAsync loop method."""

    @pytest.mark.asyncio
    async def test_loop_aggregates_and_deletes(
        self, influxdb_settings, price_settings, mock_event_bus, mock_influxdb_client
    ):
        """Test loop method performs aggregation and retention."""
        mock_sync, mock_async = mock_influxdb_client

        mock_query_api = MagicMock()
        mock_query_api.query = AsyncMock(return_value=[])
        mock_async.query_api = MagicMock(return_value=mock_query_api)

        mock_delete_api = MagicMock()
        mock_sync.delete_api.return_value = mock_delete_api

        influxdb = InfluxDBAsync(influxdb_settings, price_settings, mock_event_bus)
        influxdb.client_async = mock_async

        # Cache the aggregate query
        influxdb.flux_cache["aggregate"] = "aggregate query"

        await influxdb.loop(None)

        # Should have queried for aggregation
        mock_query_api.query.assert_called_once()

        # Should have deleted old raw data
        mock_delete_api.delete.assert_called()

        # Should have emitted aggregated event
        mock_event_bus.emit.assert_called_once()
        call_args = mock_event_bus.emit.call_args
        assert isinstance(call_args[0][0], InfluxDBAggregatedEvent)


class TestInfluxDBAsyncClose:
    """Tests for InfluxDBAsync close method."""

    @pytest.mark.asyncio
    async def test_close_closes_async_client(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test close method closes async client."""
        mock_sync, mock_async = mock_influxdb_client

        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = mock_async

        await influxdb.close()

        mock_async.close.assert_called_once()
        assert influxdb.client_async is None

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test close when async client is None."""
        influxdb = InfluxDBAsync(influxdb_settings, price_settings)
        influxdb.client_async = None

        # Should not raise
        await influxdb.close()


class TestInfluxDBAsyncFluxQuery:
    """Tests for InfluxDBAsync flux query caching."""

    def test_get_flux_query_uses_cached_query(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test _get_flux_query uses already cached queries."""
        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        # Pre-cache a query that has already been processed
        influxdb.flux_cache["test"] = "SELECT * FROM test WHERE bucket = 'test_bucket'"

        result = influxdb._get_flux_query("test")

        # Should return the cached query
        assert result == "SELECT * FROM test WHERE bucket = 'test_bucket'"

    def test_get_flux_query_with_replacements(
        self, influxdb_settings, price_settings, mock_influxdb_client
    ):
        """Test _get_flux_query with additional replacements."""
        influxdb = InfluxDBAsync(influxdb_settings, price_settings)

        influxdb.flux_cache["test"] = "SELECT * WHERE value = '{{VALUE}}'"

        result = influxdb._get_flux_query("test", {"VALUE": "42"})

        assert "42" in result
