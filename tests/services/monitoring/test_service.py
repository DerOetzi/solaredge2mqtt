"""Tests for MonitoringSite service with mocking."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, RequestInfo

from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.services.monitoring import MonitoringSite
from solaredge2mqtt.services.monitoring.models import LogicalModule
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings


@pytest.fixture
def mock_monitoring_settings():
    """Create mock monitoring settings."""
    settings = MagicMock(spec=MonitoringSettings)
    settings.site_id = "12345"
    settings.username = "test_user"
    settings.password = MagicMock()
    settings.password.get_secret_value.return_value = "test_password"
    settings.retain = False
    return settings


@pytest.fixture
def mock_influxdb():
    """Create mock InfluxDB client."""
    influxdb = AsyncMock()
    influxdb.write_points = AsyncMock()
    return influxdb


class TestMonitoringSiteInit:
    """Tests for MonitoringSite initialization."""

    def test_init(self, mock_monitoring_settings, mock_event_bus, mock_influxdb):
        """Test MonitoringSite initialization."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        assert site.settings is mock_monitoring_settings
        assert site.event_bus is mock_event_bus
        assert site.influxdb is mock_influxdb

    def test_init_without_influxdb(self, mock_monitoring_settings, mock_event_bus):
        """Test MonitoringSite initialization without InfluxDB."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, None)

        assert site.influxdb is None

    def test_subscribes_to_events(self, mock_monitoring_settings, mock_event_bus):
        """Test MonitoringSite subscribes to 15min interval event."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, None)

        mock_event_bus.subscribe.assert_called()


class TestMonitoringSiteLogin:
    """Tests for MonitoringSite login."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test successful login."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)
        site._post = AsyncMock(return_value="success")

        await site.login()

        site._post.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_failure(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test login failure raises ConfigurationException."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "http://test.com"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=401,
        )
        site._post = AsyncMock(side_effect=error)

        with pytest.raises(ConfigurationException):
            await site.login()

    @pytest.mark.asyncio
    async def test_login_timeout(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test login timeout raises ConfigurationException."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)
        site._post = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(ConfigurationException):
            await site.login()


class TestMonitoringSiteMergeModules:
    """Tests for MonitoringSite merge_modules."""

    def test_merge_modules(self):
        """Test merge_modules combines energy and power data."""
        # Create mock module
        mock_module = MagicMock(spec=LogicalModule)
        mock_module.power = None

        energies = {"SN123": mock_module}
        powers = {"SN123": {datetime.now(timezone.utc): 100.0}}

        result = MonitoringSite.merge_modules(energies, powers)

        assert "SN123" in result
        assert result["SN123"].power is not None

    def test_merge_modules_no_power(self):
        """Test merge_modules when module has no power data."""
        mock_module = MagicMock(spec=LogicalModule)
        mock_module.power = None

        energies = {"SN123": mock_module}
        powers = {}

        result = MonitoringSite.merge_modules(energies, powers)

        assert "SN123" in result


class TestMonitoringSiteSaveToInfluxDB:
    """Tests for MonitoringSite save_to_influxdb."""

    @pytest.mark.asyncio
    async def test_save_to_influxdb(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test save_to_influxdb writes points."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        # Create mock module with power data
        mock_info = MagicMock()
        mock_info.serialnumber = "SN123"
        mock_info.name = "Module 1"
        mock_info.identifier = "ID123"

        mock_module = MagicMock()
        mock_module.info = mock_info
        mock_module.power = {datetime.now(timezone.utc): 100.0}

        await site.save_to_influxdb({"SN123": mock_module})

        mock_influxdb.write_points.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_to_influxdb_none(
        self, mock_monitoring_settings, mock_event_bus
    ):
        """Test save_to_influxdb does nothing when influxdb is None."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, None)

        # Should not raise
        await site.save_to_influxdb({})


class TestMonitoringSitePublishMQTT:
    """Tests for MonitoringSite publish_mqtt."""

    @pytest.mark.asyncio
    async def test_publish_mqtt(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test publish_mqtt emits events."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        # Create mock module
        mock_info = MagicMock()
        mock_info.serialnumber = "SN123"

        mock_module = MagicMock()
        mock_module.info = mock_info
        mock_module.energy = 1000

        await site.publish_mqtt({"SN123": mock_module}, 0, 0)

        # Should emit events for module and total
        assert mock_event_bus.emit.call_count == 2


class TestMonitoringSiteGetData:
    """Tests for MonitoringSite get_data."""

    @pytest.mark.asyncio
    async def test_get_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_data orchestrates data retrieval."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        # Mock the sub-methods
        site.get_modules_energy = AsyncMock(return_value={})
        site.get_modules_power = AsyncMock(return_value={})
        site.save_to_influxdb = AsyncMock()
        site.publish_mqtt = AsyncMock()

        await site.get_data(None)

        site.get_modules_energy.assert_called_once()
        site.get_modules_power.assert_called_once()
        site.save_to_influxdb.assert_called_once()
        site.publish_mqtt.assert_called_once()


class TestMonitoringSiteGetModulesEnergy:
    """Tests for MonitoringSite get_modules_energy."""

    @pytest.mark.asyncio
    async def test_get_modules_energy_none_response(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_energy raises when response is None."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)
        site._get_logical = AsyncMock(return_value=None)

        with pytest.raises(InvalidDataException):
            await site.get_modules_energy()


class TestMonitoringSiteGetModulesPower:
    """Tests for MonitoringSite get_modules_power."""

    @pytest.mark.asyncio
    async def test_get_modules_power_none_response(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_power raises when response is None."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)
        site._get_playback = AsyncMock(return_value=None)

        with pytest.raises(InvalidDataException):
            await site.get_modules_power()


class TestMonitoringSiteGetLogical:
    """Tests for MonitoringSite _get_logical."""

    @pytest.mark.asyncio
    async def test_get_logical_needs_login(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_logical logs in if no CSRF token."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)
        site.cookie_exists = MagicMock(return_value=False)
        site.login = AsyncMock()
        site.get_cookie = MagicMock(return_value="test_token")
        site._get = AsyncMock(return_value={"result": "data"})

        result = await site._get_logical()

        site.login.assert_called_once()
        assert result == {"result": "data"}

    @pytest.mark.asyncio
    async def test_get_logical_error(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_logical raises on error."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)
        site.cookie_exists = MagicMock(return_value=True)
        site.get_cookie = MagicMock(return_value="test_token")

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "http://test.com"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=500,
        )
        site._get = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException):
            await site._get_logical()
