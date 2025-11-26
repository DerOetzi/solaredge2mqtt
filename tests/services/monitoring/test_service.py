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

# Date format used by SolarEdge monitoring API
MONITORING_DATE_FORMAT = "%a %b %d %H:%M:%S GMT %Y"
SAMPLE_PLAYBACK_DATE = "Mon Jan 01 12:00:00 GMT 2024"


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


class TestMonitoringSiteGetPlayback:
    """Tests for MonitoringSite _get_playback."""

    @pytest.mark.asyncio
    async def test_get_playback_error(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_playback raises on error."""
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
        site._post = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException):
            await site._get_playback()


class TestMonitoringSiteParseInverters:
    """Tests for MonitoringSite _parse_inverters."""

    def test_parse_inverters(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_inverters parses inverter data."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        inverter_objs = [
            {
                "data": {
                    "id": 1,
                    "name": "Inverter 1",
                    "serialNumber": "SN123",
                    "key": "INV1",
                    "type": "INVERTER",
                },
                "children": [],
            }
        ]
        reporters_data = {
            "1": {"unscaledEnergy": 1000},
        }

        result = site._parse_inverters(inverter_objs, reporters_data)

        assert len(result) == 1
        assert result[0].info.serialnumber == "SN123"

    def test_parse_inverters_unknown_type(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_inverters logs unknown type."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        inverter_objs = [
            {
                "data": {
                    "id": 2,
                    "name": "Unknown Device",
                    "serialNumber": "SN456",
                    "key": "UNK1",
                    "type": "UNKNOWN_TYPE",
                },
                "children": [],
            }
        ]
        reporters_data = {}

        result = site._parse_inverters(inverter_objs, reporters_data)

        # Should skip unknown types
        assert len(result) == 0


class TestMonitoringSiteParseStrings:
    """Tests for MonitoringSite _parse_strings."""

    def test_parse_strings(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_strings parses string data."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        inverter = MagicMock()
        inverter.strings = []

        string_objs = [
            {
                "data": {
                    "id": 10,
                    "name": "String 1",
                    "serialNumber": "STR1",
                    "key": "STR1",
                    "type": "STRING",
                },
                "children": [],
            }
        ]
        reporters_data = {
            "10": {"unscaledEnergy": 500},
        }

        site._parse_strings(inverter, string_objs, reporters_data)

        assert len(inverter.strings) == 1


class TestMonitoringSiteParsePanels:
    """Tests for MonitoringSite _parse_panels."""

    def test_parse_panels(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_panels parses panel data."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        string = MagicMock()
        string.modules = []

        panel_objs = [
            {
                "data": {
                    "id": 100,
                    "name": "Panel 1",
                    "serialNumber": "PAN1",
                    "key": "PAN1",
                    "type": "PANEL",
                },
            }
        ]
        reporters_data = {
            "100": {"unscaledEnergy": 100},
        }

        site._parse_panels(string, panel_objs, reporters_data)

        assert len(string.modules) == 1


class TestMonitoringSiteGetModulesEnergyFull:
    """Tests for MonitoringSite get_modules_energy with full parsing."""

    @pytest.mark.asyncio
    async def test_get_modules_energy_full(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_energy with full data parsing."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        logical_response = {
            "logicalTree": {
                "children": [
                    {
                        "data": {
                            "id": 1,
                            "name": "Inverter 1",
                            "serialNumber": "INV1",
                            "key": "INV1",
                            "type": "INVERTER",
                        },
                        "children": [
                            {
                                "data": {
                                    "id": 10,
                                    "name": "String 1",
                                    "serialNumber": "STR1",
                                    "key": "STR1",
                                    "type": "STRING",
                                },
                                "children": [
                                    {
                                        "data": {
                                            "id": 100,
                                            "name": "Panel 1",
                                            "serialNumber": "PAN1",
                                            "key": "PAN1",
                                            "type": "PANEL",
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            "reportersData": {
                "1": {"unscaledEnergy": 1000},
                "10": {"unscaledEnergy": 500},
                "100": {"unscaledEnergy": 100},
            },
        }
        site._get_logical = AsyncMock(return_value=logical_response)

        result = await site.get_modules_energy()

        assert "100" in result


class TestMonitoringSiteGetModulesPowerFull:
    """Tests for MonitoringSite get_modules_power with full parsing."""

    @pytest.mark.asyncio
    async def test_get_modules_power_full(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_power with full data parsing."""
        site = MonitoringSite(mock_monitoring_settings, mock_event_bus, mock_influxdb)

        playback_response = {
            "reportersData": {
                SAMPLE_PLAYBACK_DATE: {
                    "group1": [
                        {"key": "PAN1", "value": "100.5"},
                        {"key": "PAN2", "value": "95.3"},
                    ]
                }
            }
        }
        site._get_playback = AsyncMock(return_value=playback_response)

        result = await site.get_modules_power()

        assert "PAN1" in result
        assert "PAN2" in result
