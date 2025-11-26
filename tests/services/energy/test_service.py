"""Tests for EnergyService with mocking."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.energy import EnergyService
from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.energy.models import HistoricPeriod, HistoricQuery
from solaredge2mqtt.services.energy.settings import EnergySettings


@pytest.fixture
def mock_energy_settings():
    """Create mock energy settings."""
    settings = MagicMock(spec=EnergySettings)
    settings.retain = False
    return settings


@pytest.fixture
def mock_influxdb():
    """Create mock InfluxDB client."""
    influxdb = AsyncMock()
    influxdb.query_timeunit = AsyncMock()
    return influxdb


class TestEnergyServiceInit:
    """Tests for EnergyService initialization."""

    def test_init(self, mock_energy_settings, mock_event_bus, mock_influxdb):
        """Test EnergyService initialization."""
        service = EnergyService(mock_energy_settings, mock_event_bus, mock_influxdb)

        assert service.settings is mock_energy_settings
        assert service.event_bus is mock_event_bus
        assert service.influxdb is mock_influxdb

    def test_subscribes_to_events(
        self, mock_energy_settings, mock_event_bus, mock_influxdb
    ):
        """Test EnergyService subscribes to influxdb aggregated event."""
        service = EnergyService(mock_energy_settings, mock_event_bus, mock_influxdb)

        mock_event_bus.subscribe.assert_called()


class TestEnergyServiceReadHistoricEnergy:
    """Tests for EnergyService read_historic_energy."""

    @pytest.mark.asyncio
    async def test_read_historic_energy_success(
        self, mock_energy_settings, mock_event_bus, mock_influxdb
    ):
        """Test successful energy reading."""
        from datetime import datetime, timezone

        service = EnergyService(mock_energy_settings, mock_event_bus, mock_influxdb)

        # Mock query result with valid record data
        mock_record = {
            "_start": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "_stop": datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
            "pv_production": 10.5,
            "inverter_production": 9.8,
            "inverter_consumption": 0.5,
            "inverter_dc_power": 100.0,
            "inverter_pv_production": 8.0,
            "inverter_battery_production": 1.8,
            "grid_delivery": 5.0,
            "grid_consumption": 2.0,
            "battery_charge": 1.0,
            "battery_discharge": 0.5,
            "consumer_house": 4.0,
            "consumer_evcharger": 0.0,
            "consumer_inverter": 0.3,
            "consumer_total": 4.3,
            "consumer_used_production": 4.8,
            "consumer_used_pv_production": 3.5,
            "consumer_used_battery_production": 1.3,
        }

        # Return data for first period, None for others to test both paths
        mock_influxdb.query_timeunit.return_value = [mock_record]

        await service.read_historic_energy(None)

        # Should emit events for each period that returned data
        assert mock_event_bus.emit.call_count > 0

    @pytest.mark.asyncio
    async def test_read_historic_energy_no_data_last_query(
        self, mock_energy_settings, mock_event_bus, mock_influxdb
    ):
        """Test reading energy with no data for LAST query type."""
        service = EnergyService(mock_energy_settings, mock_event_bus, mock_influxdb)

        # Return None for all queries
        mock_influxdb.query_timeunit.return_value = None

        # Should not raise for LAST query type - just skip
        # But will raise for other query types
        with pytest.raises(InvalidDataException):
            await service.read_historic_energy(None)

    @pytest.mark.asyncio
    async def test_read_historic_energy_emits_events(
        self, mock_energy_settings, mock_event_bus, mock_influxdb
    ):
        """Test read_historic_energy emits correct events."""
        from datetime import datetime, timezone

        service = EnergyService(mock_energy_settings, mock_event_bus, mock_influxdb)

        mock_record = {
            "_start": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "_stop": datetime(2024, 1, 1, 23, 59, tzinfo=timezone.utc),
            "pv_production": 10.5,
            "inverter_production": 9.8,
            "inverter_consumption": 0.5,
            "inverter_dc_power": 100.0,
            "inverter_pv_production": 8.0,
            "inverter_battery_production": 1.8,
            "grid_delivery": 5.0,
            "grid_consumption": 2.0,
            "battery_charge": 1.0,
            "battery_discharge": 0.5,
            "consumer_house": 4.0,
            "consumer_evcharger": 0.0,
            "consumer_inverter": 0.3,
            "consumer_total": 4.3,
            "consumer_used_production": 4.8,
            "consumer_used_pv_production": 3.5,
            "consumer_used_battery_production": 1.3,
        }
        mock_influxdb.query_timeunit.return_value = [mock_record]

        await service.read_historic_energy(None)

        # Check that EnergyReadEvent and MQTTPublishEvent were emitted
        emit_calls = mock_event_bus.emit.call_args_list
        event_types = [type(call[0][0]) for call in emit_calls]

        assert EnergyReadEvent in event_types
        assert MQTTPublishEvent in event_types
