"""Tests for WallboxClient with mocking."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.services.wallbox import WallboxClient
from solaredge2mqtt.services.wallbox.events import WallboxReadEvent
from solaredge2mqtt.services.wallbox.settings import WallboxSettings


@pytest.fixture
def wallbox_settings():
    """Create WallboxSettings for testing."""
    settings = MagicMock(spec=WallboxSettings)
    settings.host = "192.168.1.100"
    settings.serial = "CHARGER123"
    settings.password = MagicMock()
    settings.password.get_secret_value.return_value = "test_password"
    settings.retain = False
    return settings


@pytest.fixture
def mock_http_client():
    """Mock HTTP client methods."""
    with patch.object(WallboxClient, "_get", new_callable=AsyncMock) as mock_get, \
         patch.object(WallboxClient, "_post", new_callable=AsyncMock) as mock_post:
        yield mock_get, mock_post


class TestWallboxClientInit:
    """Tests for WallboxClient initialization."""

    def test_wallbox_client_init(self, wallbox_settings, mock_event_bus):
        """Test WallboxClient initialization."""
        client = WallboxClient(wallbox_settings, mock_event_bus)

        assert client.settings is wallbox_settings
        assert client.event_bus is mock_event_bus
        assert client.authorization is None


class TestWallboxClientLogin:
    """Tests for WallboxClient login."""

    @pytest.mark.asyncio
    async def test_login_success(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test successful login."""
        mock_get, mock_post = mock_http_client

        # Mock successful login response
        mock_post.return_value = {
            "accessToken": "test_access_token_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.signature",
            "refreshToken": "test_refresh_token_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.signature",
        }

        client = WallboxClient(wallbox_settings, mock_event_bus)

        # Mock get_exp_claim
        with patch.object(
            client.__class__.__bases__[0], "_post", new_callable=AsyncMock
        ) as base_post:
            base_post.return_value = mock_post.return_value
            await client.login()

    @pytest.mark.asyncio
    async def test_login_failure_none_response(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test login failure with None response."""
        mock_get, mock_post = mock_http_client
        mock_post.return_value = None

        client = WallboxClient(wallbox_settings, mock_event_bus)

        with pytest.raises(ConfigurationException) as exc_info:
            await client.login()

        assert exc_info.value.component == "wallbox"


class TestWallboxClientGetAccess:
    """Tests for WallboxClient _get_access."""

    @pytest.mark.asyncio
    async def test_get_access_no_authorization(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _get_access calls login when no authorization."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.login = AsyncMock()
        client.authorization = None

        await client._get_access()

        client.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_token_expired(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _get_access calls login when access token expired."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.login = AsyncMock()

        # Create mock authorization with expired tokens
        mock_auth = MagicMock()
        mock_auth.access_token_expires = int(time.time()) - 100  # Expired
        mock_auth.refresh_token_expires = int(time.time()) - 100  # Expired
        client.authorization = mock_auth

        await client._get_access()

        client.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_refresh_token(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _get_access refreshes token when access expired but refresh valid."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._refresh_token = AsyncMock()
        client.login = AsyncMock()

        # Create mock authorization with expired access but valid refresh
        mock_auth = MagicMock()
        mock_auth.access_token_expires = int(time.time()) - 100  # Expired
        mock_auth.refresh_token_expires = int(time.time()) + 3600  # Valid
        client.authorization = mock_auth

        await client._get_access()

        client._refresh_token.assert_called_once()
        client.login.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_access_token_valid(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _get_access does nothing when token is valid."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.login = AsyncMock()
        client._refresh_token = AsyncMock()

        # Create mock authorization with valid tokens
        mock_auth = MagicMock()
        mock_auth.access_token_expires = int(time.time()) + 3600  # Valid
        mock_auth.refresh_token_expires = int(time.time()) + 3600  # Valid
        client.authorization = mock_auth

        await client._get_access()

        client.login.assert_not_called()
        client._refresh_token.assert_not_called()


class TestWallboxClientRefreshToken:
    """Tests for WallboxClient _refresh_token."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test successful token refresh."""
        mock_get, mock_post = mock_http_client
        mock_post.return_value = {"accessToken": "new_access_token"}

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.authorization = MagicMock()
        client.authorization.refresh_token = "old_refresh_token"

        await client._refresh_token()

        assert client.authorization.access_token == "new_access_token"


class TestWallboxClientGetData:
    """Tests for WallboxClient get_data."""

    @pytest.mark.asyncio
    async def test_get_data_success(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test successful get_data."""
        mock_get, mock_post = mock_http_client

        # Mock wallbox API response
        mock_get.return_value = {
            "wallboxPower": 7400,
            "state": "CHARGING",
            "connectedVehicle": True,
        }

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._get_access = AsyncMock()
        client.authorization = MagicMock()
        client.authorization.access_token = "test_token"

        with patch(
            "solaredge2mqtt.services.wallbox.WallboxAPI"
        ) as mock_wallbox_api:
            mock_wallbox_instance = MagicMock()
            mock_wallbox_instance.power = 7400
            mock_wallbox_instance.state = "CHARGING"
            mock_wallbox_api.return_value = mock_wallbox_instance

            result = await client.get_data()

            assert result is mock_wallbox_instance
            mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_data_none_response(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test get_data raises when response is None."""
        mock_get, mock_post = mock_http_client
        mock_get.return_value = None

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._get_access = AsyncMock()
        client.authorization = MagicMock()
        client.authorization.access_token = "test_token"

        with pytest.raises(InvalidDataException):
            await client.get_data()
