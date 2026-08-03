"""Tests for MonitoringSite service with mocking."""

import asyncio
from datetime import datetime, timezone
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientResponseError, RequestInfo

from solaredge2mqtt.core.exceptions import (
    ConfigurationException,
    InvalidDataException,
)
from solaredge2mqtt.core.timer.events import Interval15MinTriggerEvent
from solaredge2mqtt.services.monitoring import MonitoringSite
from solaredge2mqtt.services.monitoring.models import LogicalModule
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings


@pytest.fixture
def mock_monitoring_settings():
    """Create mock monitoring settings."""
    settings = MagicMock(spec=MonitoringSettings)
    settings.site_id = MagicMock()
    settings.site_id.get_secret_value.return_value = "12345"
    settings.username = "test_user"
    settings.password = MagicMock()
    settings.password.get_secret_value.return_value = "test_password"
    settings.retain = False
    settings.debounce_cycles = 0
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
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        assert site.settings is mock_monitoring_settings
        mock_event_bus.register.assert_called_once_with(site)
        assert site.influxdb is mock_influxdb

    def test_init_without_influxdb(self, mock_monitoring_settings, mock_event_bus):
        """Test MonitoringSite initialization without InfluxDB."""
        site = MonitoringSite(mock_monitoring_settings, None)

        assert site.influxdb is None

    def test_subscribes_to_events(self, mock_monitoring_settings, mock_event_bus):
        """Test MonitoringSite subscribes to 15min interval event."""
        MonitoringSite(mock_monitoring_settings, None)

        mock_event_bus.register.assert_called_once()


class TestMonitoringSiteLogin:
    """Tests for MonitoringSite login."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test successful login returns (csrf_token, remember_me_cookie) tuple."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._post = AsyncMock(return_value="success")
        site.get_cookie = MagicMock(
            side_effect=[None, None, "csrf-token", "remember-me-val"]
        )

        token, remember_me = await site.login()

        site._post.assert_called()
        assert token == "csrf-token"
        assert remember_me == "remember-me-val"

    @pytest.mark.asyncio
    async def test_login_returns_existing_token_without_post(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test login returns existing tokens as tuple without HTTP request."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._post = AsyncMock()
        site.get_cookie = MagicMock(return_value="existing-csrf-token")

        token, remember_me = await site.login()

        site._post.assert_not_called()
        assert token == "existing-csrf-token"
        assert remember_me == "existing-csrf-token"

    @pytest.mark.asyncio
    async def test_login_missing_csrf_token_after_post(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test login raises when CSRF token is missing after POST."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._post = AsyncMock(return_value="success")
        site.get_cookie = MagicMock(side_effect=[None, None, None, None])

        with pytest.raises(ConfigurationException):
            await site.login()

    @pytest.mark.asyncio
    async def test_login_failure(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test login failure raises ConfigurationException."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://test.com"

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
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._post = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(ConfigurationException):
            await site.login()


class TestMonitoringSiteGetModules:
    """Tests for MonitoringSite.get_modules (pure read, no EventBus/InfluxDB)."""

    @pytest.mark.asyncio
    async def test_get_modules_merges_energy_and_power_without_side_effects(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """get_modules fetches+merges data and emits nothing on the EventBus."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        mock_module: LogicalModule = cast(LogicalModule, MagicMock(spec=LogicalModule))
        mock_module.power = None
        site.get_modules_energy = AsyncMock(return_value={"SN123": mock_module})
        site.get_modules_power = AsyncMock(
            return_value={"SN123": {datetime.now(timezone.utc): 100.0}}
        )

        result = await site.get_modules()

        assert "SN123" in result
        assert result["SN123"].power is not None
        mock_event_bus.emit.assert_not_called()


class TestMonitoringSiteMergeModules:
    """Tests for MonitoringSite merge_modules."""

    def test_merge_modules(self):
        """Test merge_modules combines energy and power data."""
        # Create mock module
        mock_module: LogicalModule = cast(LogicalModule, MagicMock(spec=LogicalModule))
        mock_module.power = None

        energies = {"SN123": mock_module}
        powers = {"SN123": {datetime.now(timezone.utc): 100.0}}

        result = MonitoringSite.merge_modules(energies, powers)

        assert "SN123" in result
        assert result["SN123"].power is not None

    def test_merge_modules_no_power(self):
        """Test merge_modules when module has no power data."""
        mock_module: LogicalModule = cast(LogicalModule, MagicMock(spec=LogicalModule))
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
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

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
        site = MonitoringSite(mock_monitoring_settings, None)

        # Should not raise
        await site.save_to_influxdb({})


class TestMonitoringSitePublishMQTT:
    """Tests for MonitoringSite publish_mqtt."""

    @pytest.mark.asyncio
    async def test_publish_mqtt(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test publish_mqtt emits events."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

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
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        # Mock the sub-methods
        site.get_modules_energy = AsyncMock(return_value={})
        site.get_modules_power = AsyncMock(return_value={})
        site.save_to_influxdb = AsyncMock()
        site.publish_mqtt = AsyncMock()

        await site.get_data(Interval15MinTriggerEvent())

        site.get_modules_energy.assert_called_once()
        site.get_modules_power.assert_called_once()
        site.save_to_influxdb.assert_called_once()
        site.publish_mqtt.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_data_sets_offline_state_on_known_errors(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """get_data should emit monitoring offline event on data errors."""
        from solaredge2mqtt.services.monitoring.events import MonitoringOfflineEvent

        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site.get_modules_energy = AsyncMock(
            side_effect=InvalidDataException("unable to read")
        )

        with pytest.raises(InvalidDataException):
            await site.get_data(Interval15MinTriggerEvent())

        # Check that MonitoringOfflineEvent was emitted
        emit_calls = mock_event_bus.emit.call_args_list
        assert any(
            isinstance(call[0][0], MonitoringOfflineEvent) for call in emit_calls
        )


class TestMonitoringSiteGetLogical:
    """Tests for MonitoringSite _get_logical."""

    @pytest.mark.asyncio
    async def test_get_logical_needs_login(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_logical calls login via _add_login_headers."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "test_token"})
        site._get = AsyncMock(return_value={"result": "data"})

        result = await site._get_logical()

        site._add_login_headers.assert_called_once()
        assert result == {"result": "data"}

    @pytest.mark.asyncio
    async def test_get_logical_error(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_logical raises on error."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site.cookie_exists = MagicMock(return_value=True)
        site.get_cookie = MagicMock(return_value="test_token")

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://test.com"

        error = ClientResponseError(
            request_info=mock_request_info,
            history=(),
            status=500,
        )
        site._get = AsyncMock(side_effect=error)

        with pytest.raises(InvalidDataException):
            await site._get_logical()

    @pytest.mark.asyncio
    async def test_get_logical_non_dict_response_raises_invalid_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_logical raises on non-dict response payload."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "test_token"})
        site._get = AsyncMock(return_value=["unexpected", "list"])

        with pytest.raises(InvalidDataException) as exc_info:
            await site._get_logical()

        assert "Unexpected response format" in exc_info.value.message


class TestMonitoringSiteGetEnergyByInverter:
    """Tests for MonitoringSite _get_energy_by_inverter."""

    @pytest.mark.asyncio
    async def test_empty_serials_returns_empty_without_request(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_energy_by_inverter short-circuits when there are no inverters."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock()
        site._get = AsyncMock()

        result = await site._get_energy_by_inverter([])

        assert result == {}
        site._get.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_indexes_response(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_energy_by_inverter parses and indexes a valid response."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(
            return_value={
                "inverters": [
                    {
                        "serial": "INV1",
                        "energy": {"value": 1000.0, "unit": "watt-hour"},
                        "strings": [
                            {
                                "energy": {"value": 500.0, "unit": "watt-hour"},
                                "stringRelativeOrder": 2,
                            }
                        ],
                        "optimizers": [
                            {
                                "serial": "PAN1-C1",
                                "energy": {"value": 100.0, "unit": "watt-hour"},
                            }
                        ],
                    }
                ]
            }
        )

        result = await site._get_energy_by_inverter(["INV1"])

        assert result["INV1"]["energy"] == pytest.approx(1000.0)
        assert result["INV1"]["strings"][2] == pytest.approx(500.0)
        assert result["INV1"]["optimizers"]["PAN1-C1"] == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_error_raises_invalid_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_energy_by_inverter raises InvalidDataException on HTTP error."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://test.com"
        site._get = AsyncMock(
            side_effect=ClientResponseError(
                request_info=mock_request_info, history=(), status=500
            )
        )

        with pytest.raises(InvalidDataException):
            await site._get_energy_by_inverter(["INV1"])

    @pytest.mark.asyncio
    async def test_non_dict_response_raises_invalid_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _get_energy_by_inverter raises on non-dict response payload."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(return_value=["unexpected", "list"])

        with pytest.raises(InvalidDataException):
            await site._get_energy_by_inverter(["INV1"])


class TestMonitoringSiteIndexEnergyByInverter:
    """Tests for MonitoringSite._index_energy_by_inverter."""

    def test_skips_inverter_without_serial(self):
        result = MonitoringSite._index_energy_by_inverter(
            {"inverters": [{"energy": {"value": 1.0}}]}
        )
        assert result == {}

    def test_missing_energy_value_is_none(self):
        result = MonitoringSite._index_energy_by_inverter(
            {"inverters": [{"serial": "INV1"}]}
        )
        assert result["INV1"]["energy"] is None
        assert result["INV1"]["strings"] == {}
        assert result["INV1"]["optimizers"] == {}


class TestMonitoringSiteLoadStructure:
    """Tests for MonitoringSite._load_structure."""

    @pytest.mark.asyncio
    async def test_success_caches_structure(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _load_structure caches siteStructure from _get_logical."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._get_logical = AsyncMock(return_value={"siteStructure": {"children": []}})

        await site._load_structure()

        assert site._cached_structure == {"children": []}

    @pytest.mark.asyncio
    async def test_error_logs_warning_no_raise(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _load_structure swallows errors, leaving cache empty."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._get_logical = AsyncMock(
            side_effect=InvalidDataException("unable to read")
        )

        await site._load_structure()

        assert site._cached_structure is None


def make_folder(name: str, children: list[dict]) -> dict:
    return {"type": "FOLDER", "name": name, "children": children}


class TestMonitoringSiteParseInverters:
    """Tests for MonitoringSite _parse_inverters."""

    def test_parse_inverters(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_inverters parses inverter data nested under a FOLDER."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        site_structure = {
            "children": [
                make_folder(
                    "INVERTER",
                    [
                        {
                            "name": "Inverter 1",
                            "serial": "SN123",
                            "type": "INVERTER",
                            "properties": {"identifier": "1"},
                            "children": [],
                        }
                    ],
                )
            ]
        }

        result = site._parse_inverters(site_structure, {})

        assert len(result) == 1
        assert result[0].info.serialnumber == "SN123"

    def test_parse_inverters_with_energy(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_inverters attaches energy from the energy-by-inverter index."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        site_structure = {
            "children": [
                make_folder(
                    "INVERTER",
                    [
                        {
                            "name": "Inverter 1",
                            "serial": "SN123",
                            "type": "INVERTER",
                            "properties": {"identifier": "1"},
                            "children": [],
                        }
                    ],
                )
            ]
        }
        energy_by_inverter = {
            "SN123": {"energy": 1234.5, "strings": {}, "optimizers": {}}
        }

        result = site._parse_inverters(site_structure, energy_by_inverter)

        assert result[0].energy == pytest.approx(1234.5)

    def test_parse_inverters_unknown_type(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_inverters logs and skips unknown type nodes."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        site_structure = {
            "children": [
                make_folder(
                    "INVERTER",
                    [
                        {
                            "name": "Unknown Device",
                            "serial": "SN456",
                            "type": "UNKNOWN_TYPE",
                            "properties": {"identifier": "2"},
                            "children": [],
                        }
                    ],
                )
            ]
        }

        result = site._parse_inverters(site_structure, {})

        # Should skip unknown types
        assert len(result) == 0

    def test_parse_inverters_no_inverter_folder(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_inverters returns empty list when no INVERTER folder exists."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        result = site._parse_inverters({"children": []}, {})

        assert result == []


class TestMonitoringSiteFolderChildren:
    """Tests for MonitoringSite._folder_children."""

    def test_skips_non_matching_siblings_before_match(self):
        """A non-matching sibling before the target FOLDER is skipped, not returned."""
        node = {
            "children": [
                make_folder("BATTERY", [{"type": "BATTERY"}]),
                make_folder("INVERTER", [{"type": "INVERTER", "serial": "SN1"}]),
            ]
        }

        result = MonitoringSite._folder_children(node, "INVERTER")

        assert result == [{"type": "INVERTER", "serial": "SN1"}]

    def test_no_matching_folder_returns_empty(self):
        node = {"children": [make_folder("BATTERY", [{"type": "BATTERY"}])]}

        result = MonitoringSite._folder_children(node, "INVERTER")

        assert result == []


class TestMonitoringSiteParseStrings:
    """Tests for MonitoringSite _parse_strings."""

    def test_parse_strings(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_strings parses string data nested under a FOLDER."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        inverter = MagicMock()
        inverter.strings = []

        inverter_node = {
            "children": [
                make_folder(
                    "STRING",
                    [
                        {
                            "name": "String 1",
                            "type": "STRING",
                            "properties": {"identifier": "SN123_10"},
                            "children": [],
                        }
                    ],
                )
            ]
        }

        site._parse_strings(inverter, inverter_node, {}, {})

        assert len(inverter.strings) == 1

    def test_parse_strings_with_energy(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_strings attaches energy matched by stringRelativeOrder."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        inverter = MagicMock()
        inverter.strings = []

        inverter_node = {
            "children": [
                make_folder(
                    "STRING",
                    [
                        {
                            "name": "String 1",
                            "type": "STRING",
                            "order": 2,
                            "properties": {"identifier": "SN123_10"},
                            "children": [],
                        }
                    ],
                )
            ]
        }

        site._parse_strings(inverter, inverter_node, {2: 555.0}, {})

        assert inverter.strings[0].energy == pytest.approx(555.0)

    def test_parse_strings_skips_non_string_type(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_strings skips nodes inside the STRING folder with a
        mismatched type."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        inverter = MagicMock()
        inverter.strings = []

        inverter_node = {
            "children": [
                make_folder(
                    "STRING",
                    [
                        {
                            "name": "Unexpected",
                            "type": "UNKNOWN_TYPE",
                            "properties": {"identifier": "X"},
                            "children": [],
                        }
                    ],
                )
            ]
        }

        site._parse_strings(inverter, inverter_node, {}, {})

        assert inverter.strings == []


class TestMonitoringSiteParsePanels:
    """Tests for MonitoringSite _parse_panels."""

    def test_parse_panels(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_panels parses optimizer data nested under a FOLDER."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        string = MagicMock()
        string.modules = []

        string_node = {
            "children": [
                make_folder(
                    "OPTIMIZER",
                    [
                        {
                            "name": "Optimizer 1",
                            "serial": "PAN1-C1",
                            "type": "OPTIMIZER",
                            "properties": {"identifier": "PAN1"},
                        }
                    ],
                )
            ]
        }

        site._parse_panels(string, string_node, {})

        assert len(string.modules) == 1

    def test_parse_panels_with_energy(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_panels attaches energy matched by optimizer serial."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        string = MagicMock()
        string.modules = []

        string_node = {
            "children": [
                make_folder(
                    "OPTIMIZER",
                    [
                        {
                            "name": "Optimizer 1",
                            "serial": "PAN1-C1",
                            "type": "OPTIMIZER",
                            "properties": {"identifier": "PAN1"},
                        }
                    ],
                )
            ]
        }

        site._parse_panels(string, string_node, {"PAN1-C1": 42.0})

        assert string.modules[0].energy == pytest.approx(42.0)

    def test_parse_panels_skips_non_optimizer_type(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test _parse_panels skips nodes inside the OPTIMIZER folder with a
        mismatched type."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        string = MagicMock()
        string.modules = []

        string_node = {
            "children": [
                make_folder(
                    "OPTIMIZER",
                    [
                        {
                            "name": "Unexpected",
                            "type": "UNKNOWN_TYPE",
                            "properties": {"identifier": "X"},
                        }
                    ],
                )
            ]
        }

        site._parse_panels(string, string_node, {})

        assert string.modules == []


class TestMonitoringSiteGetModulesEnergyFull:
    """Tests for MonitoringSite get_modules_energy with full parsing."""

    @pytest.mark.asyncio
    async def test_get_modules_energy_full(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_energy with full data parsing."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        site._cached_structure = {
            "children": [
                make_folder(
                    "INVERTER",
                    [
                        {
                            "name": "Inverter 1",
                            "serial": "INV1",
                            "type": "INVERTER",
                            "properties": {"identifier": "1"},
                            "children": [
                                make_folder(
                                    "STRING",
                                    [
                                        {
                                            "name": "String 1",
                                            "type": "STRING",
                                            "properties": {"identifier": "10"},
                                            "children": [
                                                make_folder(
                                                    "OPTIMIZER",
                                                    [
                                                        {
                                                            "name": "Panel 1",
                                                            "serial": "PAN1-C1",
                                                            "type": "OPTIMIZER",
                                                            "properties": {
                                                                "identifier": "100"
                                                            },
                                                        }
                                                    ],
                                                )
                                            ],
                                        }
                                    ],
                                )
                            ],
                        }
                    ],
                )
            ]
        }
        site._get_energy_by_inverter = AsyncMock(
            return_value={
                "INV1": {
                    "energy": 1000.0,
                    "strings": {},
                    "optimizers": {"PAN1-C1": 100.0},
                }
            }
        )

        result = await site.get_modules_energy()

        assert "100" in result
        assert result["100"].energy == pytest.approx(100.0)
        site._get_energy_by_inverter.assert_called_once_with(["INV1"])

    @pytest.mark.asyncio
    async def test_get_modules_energy_lazy_loads_structure_when_uncached(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_energy lazily loads the structure if not cached yet."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        assert site._cached_structure is None

        site._get_logical = AsyncMock(return_value={"siteStructure": {"children": []}})
        site._get_energy_by_inverter = AsyncMock(return_value={})

        result = await site.get_modules_energy()

        site._get_logical.assert_called_once()
        assert result == {}

    @pytest.mark.asyncio
    async def test_get_modules_energy_reuses_cached_structure(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_energy does not refetch structure once cached."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._cached_structure = {"children": []}

        site._get_logical = AsyncMock()
        site._get_energy_by_inverter = AsyncMock(return_value={})

        await site.get_modules_energy()

        site._get_logical.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_modules_energy_raises_when_structure_unavailable(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_energy raises if structure stays uncached after load."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._load_structure = AsyncMock()

        with pytest.raises(InvalidDataException):
            await site.get_modules_energy()


class TestMonitoringSiteGetModulesPowerFull:
    """Tests for MonitoringSite get_modules_power with full parsing."""

    @pytest.mark.asyncio
    async def test_get_modules_power_full(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_power decodes optimizers-compact into per-module power."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(
            return_value={
                "timeSlotsCount": 2,
                "optimizerSerials": ["PAN1", "PAN2"],
                "compressPowerData": [2.0, 6.0, 0, 0, 0, 0, 100.5, 101.0, 95.3, 96.0],
            }
        )

        result = await site.get_modules_power()

        assert "PAN1" in result
        assert "PAN2" in result
        assert list(result["PAN1"].values()) == [100.5, 101.0]
        assert list(result["PAN2"].values()) == [95.3, 96.0]

    @pytest.mark.asyncio
    async def test_get_modules_power_http_error_raises_invalid_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_power raises InvalidDataException on HTTP error."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://test.com"
        site._get = AsyncMock(
            side_effect=ClientResponseError(
                request_info=mock_request_info, history=(), status=500
            )
        )

        with pytest.raises(InvalidDataException):
            await site.get_modules_power()

    @pytest.mark.asyncio
    async def test_get_modules_power_non_dict_response_raises_invalid_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_power raises InvalidDataException on non-dict response."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(return_value=["unexpected", "list"])

        with pytest.raises(InvalidDataException):
            await site.get_modules_power()

    @pytest.mark.asyncio
    async def test_get_modules_power_timeout_raises_invalid_data(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """Test get_modules_power raises InvalidDataException on timeout."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(side_effect=asyncio.TimeoutError())

        with pytest.raises(InvalidDataException):
            await site.get_modules_power()


class TestMonitoringSiteDecodeOptimizersCompact:
    """Tests for MonitoringSite._decode_optimizers_compact."""

    def test_decodes_per_optimizer_hourly_power(self):
        today = datetime.now().astimezone().date()
        data = {
            "timeSlotsCount": 2,
            "optimizerSerials": ["PAN1", "PAN2"],
            "compressPowerData": [2.0, 6.0, 0, 0, 0, 0, 100.5, 101.0, 95.3, 96.0],
        }

        result = MonitoringSite._decode_optimizers_compact(data, today)

        assert list(result["PAN1"].values()) == [100.5, 101.0]
        assert list(result["PAN2"].values()) == [95.3, 96.0]

    def test_empty_serials_returns_empty(self):
        today = datetime.now().astimezone().date()
        result = MonitoringSite._decode_optimizers_compact(
            {"timeSlotsCount": 24, "optimizerSerials": [], "compressPowerData": []},
            today,
        )
        assert result == {}

    def test_missing_time_slots_returns_empty(self):
        today = datetime.now().astimezone().date()
        result = MonitoringSite._decode_optimizers_compact(
            {
                "timeSlotsCount": 0,
                "optimizerSerials": ["PAN1"],
                "compressPowerData": [2.0, 4.0, 0, 0],
            },
            today,
        )
        assert result == {}


class TestMonitoringSiteExtraBranches:
    """Extra tests to cover remaining monitoring service branches."""

    @pytest.mark.asyncio
    async def test_save_to_influxdb_skips_modules_without_power(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """save_to_influxdb ignores modules with no power data."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        with_power_info = MagicMock()
        with_power_info.serialnumber = "SN123"
        with_power_info.name = "Module 1"
        with_power_info.identifier = "ID123"
        with_power = MagicMock()
        with_power.info = with_power_info
        with_power.power = {datetime.now(timezone.utc): 111.0}

        without_power_info = MagicMock()
        without_power_info.serialnumber = "SN999"
        without_power_info.name = "Module X"
        without_power_info.identifier = "IDX"
        without_power = MagicMock()
        without_power.info = without_power_info
        without_power.power = None

        await site.save_to_influxdb({"a": with_power, "b": without_power})

        mock_influxdb.write_points.assert_called_once()
        points = mock_influxdb.write_points.call_args[0][0]
        assert len(points) == 1

    @pytest.mark.asyncio
    async def test_publish_mqtt_with_none_energy_still_emits_module_event(
        self, mock_monitoring_settings, mock_event_bus, mock_influxdb
    ):
        """publish_mqtt emits module event even when module.energy is None."""
        site = MonitoringSite(mock_monitoring_settings, mock_influxdb)

        module_info = MagicMock()
        module_info.serialnumber = "SN123"
        module = MagicMock()
        module.info = module_info
        module.energy = None

        await site.publish_mqtt({"SN123": module}, 0, 0)

        # One module publish + one total publish
        assert mock_event_bus.emit.call_count == 2


# ---------------------------------------------------------------------------
# Shared EV charger test data
# ---------------------------------------------------------------------------

SAMPLE_EV_CHARGER_DEVICE = {
    "manufacturer": "Keba AG",
    "model": "P30",
    "swVersion": "1.2.3",
    "serialNumber": "SN123456",
    "name": "EV Charger",
    "reporterId": 12345,
    "chargerStatus": "READY",
    "connectionStatus": "CONNECTED",
    "sessionActive": True,
    "sessionEnergy": 5000,
    "ratedPower": 11000.0,
    "actionOperationDetails": [{"actionOp": "OFF"}],
}

SAMPLE_DEVICES_RESPONSE = {"devicesByType": {"EV_CHARGER": [SAMPLE_EV_CHARGER_DEVICE]}}


class TestMonitoringSiteAsyncInit:
    """Tests for MonitoringSite.async_init."""

    @pytest.mark.asyncio
    async def test_async_init_calls_discover_evchargers(
        self, mock_monitoring_settings, mock_event_bus
    ):
        site = MonitoringSite(mock_monitoring_settings, None)
        site._discover_evchargers = AsyncMock()
        site._load_structure = AsyncMock()

        await site.async_init()

        site._discover_evchargers.assert_called_once()

    async def test_async_init_loads_structure(
        self, mock_monitoring_settings, mock_event_bus
    ):
        site = MonitoringSite(mock_monitoring_settings, None)
        site._discover_evchargers = AsyncMock()
        site._load_structure = AsyncMock()

        await site.async_init()

        site._load_structure.assert_called_once()


class TestMonitoringSiteDiscoverEVChargers:
    """Tests for MonitoringSite._discover_evchargers."""

    @pytest.mark.asyncio
    async def test_discover_finds_chargers_and_subscribes(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.services.monitoring.events import (
            EVChargerChargeLevelSubscribeEvent,
        )

        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(return_value=SAMPLE_DEVICES_RESPONSE)

        await site._discover_evchargers()

        assert site.found_evchargers is True
        emit_calls = mock_event_bus.emit.call_args_list
        assert any(
            isinstance(call[0][0], EVChargerChargeLevelSubscribeEvent)
            for call in emit_calls
        )

    @pytest.mark.asyncio
    async def test_discover_no_chargers_does_not_set_flag(
        self, mock_monitoring_settings, mock_event_bus
    ):
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(return_value={"devicesByType": {"EV_CHARGER": []}})

        await site._discover_evchargers()

        assert site.found_evchargers is False
        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_exception_logs_warning_no_raise(
        self, mock_monitoring_settings, mock_event_bus
    ):
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(
            side_effect=ConfigurationException("monitoring", "no login")
        )

        await site._discover_evchargers()

        assert site.found_evchargers is False

    @pytest.mark.asyncio
    async def test_discover_timeout_logs_warning_no_raise(
        self, mock_monitoring_settings, mock_event_bus
    ):
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(side_effect=asyncio.TimeoutError())

        await site._discover_evchargers()

        assert site.found_evchargers is False


class TestMonitoringSiteRefreshEVChargers:
    """Tests for MonitoringSite.refresh_evchargers."""

    @pytest.mark.asyncio
    async def test_refresh_skips_when_no_chargers_found(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.core.timer.events import Interval5MinTriggerEvent

        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock()

        await site.refresh_evchargers(Interval5MinTriggerEvent())

        site._add_login_headers.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_emits_read_publish_and_online_events(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
        from solaredge2mqtt.core.timer.events import Interval5MinTriggerEvent
        from solaredge2mqtt.services.monitoring.events import (
            EVChargerReadEvent,
            MonitoringOnlineEvent,
        )

        site = MonitoringSite(mock_monitoring_settings, None)
        site.found_evchargers = True
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._get = AsyncMock(return_value=SAMPLE_DEVICES_RESPONSE)

        await site.refresh_evchargers(Interval5MinTriggerEvent())

        emit_calls = mock_event_bus.emit.call_args_list
        types_emitted = [type(call[0][0]) for call in emit_calls]
        assert EVChargerReadEvent in types_emitted
        assert MQTTPublishEvent in types_emitted
        assert MonitoringOnlineEvent in types_emitted

    @pytest.mark.asyncio
    async def test_refresh_on_error_emits_offline_event(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.core.timer.events import Interval5MinTriggerEvent
        from solaredge2mqtt.services.monitoring.events import MonitoringOfflineEvent

        site = MonitoringSite(mock_monitoring_settings, None)
        site.found_evchargers = True
        site._add_login_headers = AsyncMock(
            side_effect=ConfigurationException("monitoring", "login fail")
        )

        await site.refresh_evchargers(Interval5MinTriggerEvent())

        emit_calls = mock_event_bus.emit.call_args_list
        assert any(
            isinstance(call[0][0], MonitoringOfflineEvent) for call in emit_calls
        )

    @pytest.mark.asyncio
    async def test_refresh_on_timeout_emits_offline_event(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from aiohttp import ClientResponseError, RequestInfo

        from solaredge2mqtt.core.timer.events import Interval5MinTriggerEvent
        from solaredge2mqtt.services.monitoring.events import MonitoringOfflineEvent

        site = MonitoringSite(mock_monitoring_settings, None)
        site.found_evchargers = True
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://test.com"
        site._get = AsyncMock(
            side_effect=ClientResponseError(
                request_info=mock_request_info, history=(), status=503
            )
        )

        await site.refresh_evchargers(Interval5MinTriggerEvent())

        emit_calls = mock_event_bus.emit.call_args_list
        assert any(
            isinstance(call[0][0], MonitoringOfflineEvent) for call in emit_calls
        )


class TestMonitoringSiteExtractEVChargers:
    """Tests for MonitoringSite._extract_evchargers static method."""

    def test_non_dict_result_returns_empty(self):
        assert MonitoringSite._extract_evchargers([]) == []

    def test_missing_devices_by_type_returns_empty(self):
        assert MonitoringSite._extract_evchargers({}) == []

    def test_devices_by_type_not_dict_returns_empty(self):
        assert MonitoringSite._extract_evchargers({"devicesByType": "bad"}) == []

    def test_chargers_not_list_returns_empty(self):
        result = MonitoringSite._extract_evchargers(
            {"devicesByType": {"EV_CHARGER": "bad"}}
        )
        assert result == []

    def test_charger_without_reporter_id_filtered_out(self):
        result = MonitoringSite._extract_evchargers(
            {"devicesByType": {"EV_CHARGER": [{"no_id": True}]}}
        )
        assert result == []

    def test_non_dict_charger_entry_filtered_out(self):
        result = MonitoringSite._extract_evchargers(
            {"devicesByType": {"EV_CHARGER": ["not_a_dict"]}}
        )
        assert result == []

    def test_valid_charger_returned(self):
        device = {"reporterId": 12345, "name": "Charger"}
        result = MonitoringSite._extract_evchargers(
            {"devicesByType": {"EV_CHARGER": [device]}}
        )
        assert result == [device]

    def test_mixed_valid_and_invalid_chargers(self):
        valid = {"reporterId": 12345}
        invalid_no_id = {"name": "No ID"}
        invalid_not_dict = "string"
        result = MonitoringSite._extract_evchargers(
            {"devicesByType": {"EV_CHARGER": [valid, invalid_no_id, invalid_not_dict]}}
        )
        assert result == [valid]


class TestMonitoringSiteHandleChargeCommand:
    """Tests for MonitoringSite.handle_charge_command."""

    @pytest.mark.asyncio
    async def test_valid_topic_calls_execute_charge_control(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.services.monitoring.events import EVChargerChargeLevelEvent
        from solaredge2mqtt.services.monitoring.inputs import EVChargerChargeLevelInput

        site = MonitoringSite(mock_monitoring_settings, None)
        site._execute_charge_control = AsyncMock()

        event = EVChargerChargeLevelEvent(
            topic="monitoring/evcharger/12345/charge_level",
            input=EVChargerChargeLevelInput(level=75),
        )
        await site.handle_charge_command(event)

        site._execute_charge_control.assert_called_once_with(12345, 75)

    @pytest.mark.asyncio
    async def test_topic_without_evcharger_segment_logs_warning(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.services.monitoring.events import EVChargerChargeLevelEvent
        from solaredge2mqtt.services.monitoring.inputs import EVChargerChargeLevelInput

        site = MonitoringSite(mock_monitoring_settings, None)
        site._execute_charge_control = AsyncMock()

        event = EVChargerChargeLevelEvent(
            topic="monitoring/other/12345/charge_level",
            input=EVChargerChargeLevelInput(level=50),
        )
        await site.handle_charge_command(event)

        site._execute_charge_control.assert_not_called()

    @pytest.mark.asyncio
    async def test_topic_with_evcharger_at_end_logs_warning(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.services.monitoring.events import EVChargerChargeLevelEvent
        from solaredge2mqtt.services.monitoring.inputs import EVChargerChargeLevelInput

        site = MonitoringSite(mock_monitoring_settings, None)
        site._execute_charge_control = AsyncMock()

        event = EVChargerChargeLevelEvent(
            topic="monitoring/evcharger",
            input=EVChargerChargeLevelInput(level=50),
        )
        await site.handle_charge_command(event)

        site._execute_charge_control.assert_not_called()

    @pytest.mark.asyncio
    async def test_topic_with_non_numeric_reporter_id_logs_warning(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.services.monitoring.events import EVChargerChargeLevelEvent
        from solaredge2mqtt.services.monitoring.inputs import EVChargerChargeLevelInput

        site = MonitoringSite(mock_monitoring_settings, None)
        site._execute_charge_control = AsyncMock()

        event = EVChargerChargeLevelEvent(
            topic="monitoring/evcharger/notanumber/charge_level",
            input=EVChargerChargeLevelInput(level=50),
        )
        await site.handle_charge_command(event)

        site._execute_charge_control.assert_not_called()


class TestMonitoringSiteClose:
    """Tests for MonitoringSite.close."""

    @pytest.mark.asyncio
    async def test_close_emits_offline_event(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from solaredge2mqtt.services.monitoring.events import MonitoringOfflineEvent

        site = MonitoringSite(mock_monitoring_settings, None)
        await site.close()

        emit_calls = mock_event_bus.emit.call_args_list
        assert any(
            isinstance(call[0][0], MonitoringOfflineEvent) for call in emit_calls
        )


class TestMonitoringSiteExecuteChargeControl:
    """Tests for MonitoringSite._execute_charge_control."""

    @pytest.mark.asyncio
    async def test_not_configured_returns_without_put(
        self, mock_monitoring_settings, mock_event_bus
    ):
        mock_monitoring_settings.is_configured = False
        site = MonitoringSite(mock_monitoring_settings, None)
        site._put = AsyncMock()

        await site._execute_charge_control(12345, 50)

        site._put.assert_not_called()

    @pytest.mark.asyncio
    async def test_passed_result_logs_success(
        self, mock_monitoring_settings, mock_event_bus
    ):
        mock_monitoring_settings.is_configured = True
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._put = AsyncMock(return_value={"status": "PASSED"})

        await site._execute_charge_control(12345, 50)

        site._put.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_passed_result_logs_warning(
        self, mock_monitoring_settings, mock_event_bus
    ):
        mock_monitoring_settings.is_configured = True
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._put = AsyncMock(return_value={"status": "FAILED"})

        await site._execute_charge_control(12345, 50)

        site._put.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_dict_result_logs_warning(
        self, mock_monitoring_settings, mock_event_bus
    ):
        mock_monitoring_settings.is_configured = True
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._put = AsyncMock(return_value=None)

        await site._execute_charge_control(12345, 50)

        site._put.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_error_logs_warning_no_raise(
        self, mock_monitoring_settings, mock_event_bus
    ):
        from aiohttp import ClientResponseError, RequestInfo

        mock_monitoring_settings.is_configured = True
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})

        mock_request_info = MagicMock(spec=RequestInfo)
        mock_request_info.real_url = "https://test.com"
        site._put = AsyncMock(
            side_effect=ClientResponseError(
                request_info=mock_request_info, history=(), status=500
            )
        )

        await site._execute_charge_control(12345, 50)

    @pytest.mark.asyncio
    async def test_timeout_logs_warning_no_raise(
        self, mock_monitoring_settings, mock_event_bus
    ):
        mock_monitoring_settings.is_configured = True
        site = MonitoringSite(mock_monitoring_settings, None)
        site._add_login_headers = AsyncMock(return_value={"X-CSRF-TOKEN": "token"})
        site._put = AsyncMock(side_effect=asyncio.TimeoutError())

        await site._execute_charge_control(12345, 50)
