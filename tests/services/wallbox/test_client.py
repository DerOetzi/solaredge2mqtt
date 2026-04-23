"""Tests for WallboxClient with mocking."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import (
    ConfigurationException,
    InvalidDataException,
)
from solaredge2mqtt.services.wallbox import WallboxClient
from solaredge2mqtt.services.wallbox.settings import WallboxSettings


@pytest.fixture
def wallbox_settings():
    """Create WallboxSettings for testing."""
    settings = MagicMock(spec=WallboxSettings)
    settings.host = "192.168.1.100"  # noqa: S1313
    settings.serial = MagicMock()
    settings.serial.get_secret_value.return_value = "CHARGER123"
    settings.password = MagicMock()
    settings.password.get_secret_value.return_value = "test_password"
    settings.retain = False
    return settings


@pytest.fixture
def mock_http_client():
    """Mock HTTP client methods."""
    with (
        patch.object(WallboxClient, "_get", new_callable=AsyncMock) as mock_get,
        patch.object(WallboxClient, "_post", new_callable=AsyncMock) as mock_post,
    ):
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
        _, mock_post = mock_http_client

        # Mock successful login response
        mock_post.return_value = {
            "accessToken": "test_access_token_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.signature",  # noqa: E501
            "refreshToken": "test_refresh_token_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjk5OTk5OTk5OTl9.signature",  # noqa: E501
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
        _, mock_post = mock_http_client
        mock_post.return_value = None

        client = WallboxClient(wallbox_settings, mock_event_bus)

        with pytest.raises(ConfigurationException) as exc_info:
            await client.login()

        assert exc_info.value.component == "wallbox"

    @pytest.mark.asyncio
    async def test_login_failure_timeout_raises_configuration_exception(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test login timeout is wrapped in ConfigurationException."""
        _, mock_post = mock_http_client
        mock_post.side_effect = asyncio.TimeoutError()

        client = WallboxClient(wallbox_settings, mock_event_bus)

        with pytest.raises(ConfigurationException) as exc_info:
            await client.login()

        assert exc_info.value.component == "wallbox"


class TestWallboxClientGetAccess:
    """Tests for WallboxClient _get_access."""

    @pytest.mark.asyncio
    async def test_get_access_no_authorization(self, wallbox_settings, mock_event_bus):
        """Test _get_access calls login when no authorization."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.login = AsyncMock()
        client.authorization = None

        await client._get_access()

        client.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_authorization_with_none_access_token(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _get_access calls login when access token is missing."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.login = AsyncMock()

        mock_auth = MagicMock()
        mock_auth.access_token = None
        client.authorization = mock_auth

        await client._get_access()

        client.login.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_access_token_expired(self, wallbox_settings, mock_event_bus):
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
    async def test_get_access_refresh_token(self, wallbox_settings, mock_event_bus):
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
    async def test_get_access_token_valid(self, wallbox_settings, mock_event_bus):
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
        _, mock_post = mock_http_client
        mock_post.return_value = {"accessToken": "new_access_token"}

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.authorization = MagicMock()
        client.authorization.access_token = "old_access_token"
        client.authorization.refresh_token = "old_refresh_token"

        await client._refresh_token()

        assert client.authorization.access_token == "new_access_token"
        assert client.authorization.refresh_token == "old_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_token_repeated_refresh_uses_same_refresh_token(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test repeated refresh keeps refresh token available for next call."""
        _, mock_post = mock_http_client
        mock_post.side_effect = [
            {"accessToken": "new_access_token_1"},
            {"accessToken": "new_access_token_2"},
        ]

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.authorization = MagicMock()
        client.authorization.access_token = "old_access_token"
        client.authorization.refresh_token = "old_refresh_token"

        await client._refresh_token()
        await client._refresh_token()

        assert client.authorization.access_token == "new_access_token_2"
        assert client.authorization.refresh_token == "old_refresh_token"

    @pytest.mark.asyncio
    async def test_refresh_token_missing_authorization_raises(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _refresh_token raises when there is no prior authorization."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.authorization = None

        with pytest.raises(InvalidDataException) as exc_info:
            await client._refresh_token()

        assert "Missing previous Wallbox authorization" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_refresh_token_missing_refresh_token_raises(
        self, wallbox_settings, mock_event_bus
    ):
        """Test _refresh_token raises when refresh token is missing."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.authorization = MagicMock()
        client.authorization.refresh_token = None

        with pytest.raises(InvalidDataException) as exc_info:
            await client._refresh_token()

        assert "Missing previous Wallbox authorization" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_refresh_token_none_response_raises_invalid_data(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test _refresh_token raises when refresh endpoint returns None."""
        _, mock_post = mock_http_client
        mock_post.return_value = None

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client.authorization = MagicMock()
        client.authorization.refresh_token = "old_refresh_token"

        with pytest.raises(InvalidDataException) as exc_info:
            await client._refresh_token()

        assert "No valid token refresh response" in exc_info.value.message


class TestWallboxClientGetData:
    """Tests for WallboxClient get_data."""

    @pytest.mark.asyncio
    async def test_get_data_success(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test successful get_data."""
        mock_get, _ = mock_http_client

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

        with patch("solaredge2mqtt.services.wallbox.WallboxAPI") as mock_wallbox_api:
            mock_wallbox_instance = MagicMock()
            mock_wallbox_instance.power = 7400
            mock_wallbox_instance.state = "CHARGING"
            mock_wallbox_api.from_http_response.return_value = mock_wallbox_instance

            result = await client.get_data()

            assert result is mock_wallbox_instance
            mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_data_none_response(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test get_data raises when response is None."""
        mock_get, _ = mock_http_client
        mock_get.return_value = None

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._get_access = AsyncMock()
        client.authorization = MagicMock()
        client.authorization.access_token = "test_token"

        with pytest.raises(InvalidDataException):
            await client.get_data()

    @pytest.mark.asyncio
    async def test_get_data_missing_authorization_raises(
        self, wallbox_settings, mock_event_bus
    ):
        """Test get_data raises when _get_access leaves authorization unset."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._get_access = AsyncMock()
        client.authorization = None

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_data()

        assert "Missing Wallbox authorization" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_data_missing_access_token_raises(
        self, wallbox_settings, mock_event_bus
    ):
        """Test get_data raises when authorization has no access token."""
        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._get_access = AsyncMock()
        client.authorization = MagicMock()
        client.authorization.access_token = None

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_data()

        assert "Missing Wallbox authorization" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_get_data_timeout_wrapped_as_invalid_data(
        self, wallbox_settings, mock_event_bus, mock_http_client
    ):
        """Test get_data wraps asyncio.TimeoutError from HTTP layer."""
        mock_get, _ = mock_http_client
        mock_get.side_effect = asyncio.TimeoutError()

        client = WallboxClient(wallbox_settings, mock_event_bus)
        client._get_access = AsyncMock()
        client.authorization = MagicMock()
        client.authorization.access_token = "test_token"

        with pytest.raises(InvalidDataException) as exc_info:
            await client.get_data()

        assert "Cannot read Wallbox data" in exc_info.value.message
