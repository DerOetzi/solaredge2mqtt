"""Tests for the http_async service module."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from solaredge2mqtt.services.http_async import HTTPClientAsync


class TestHTTPClientAsync:
    """Tests for HTTPClientAsync class."""

    def test_init(self):
        """Test HTTPClientAsync initialization."""
        client = HTTPClientAsync("TestService")

        assert client.service == "TestService"
        assert client.session is None

    async def test_init_creates_session(self):
        """Test init method creates session."""
        client = HTTPClientAsync("TestService")

        client.init()

        assert client.session is not None
        assert isinstance(client.session, aiohttp.ClientSession)

        # Cleanup
        await client.close()

    async def test_init_does_not_recreate_session(self):
        """Test init does not recreate existing session."""
        client = HTTPClientAsync("TestService")
        client.init()
        first_session = client.session

        client.init()

        assert client.session is first_session

        # Cleanup
        await client.close()

    async def test_close_closes_session(self):
        """Test close method closes session."""
        client = HTTPClientAsync("TestService")
        client.init()

        await client.close()

        assert client.session is None

    async def test_close_no_session(self):
        """Test close method handles no session gracefully."""
        client = HTTPClientAsync("TestService")

        await client.close()

        assert client.session is None

    def test_cookie_exists_no_session(self):
        """Test cookie_exists returns False when no session."""
        client = HTTPClientAsync("TestService")

        result = client.cookie_exists("CSRF-TOKEN")

        assert result is False

    def test_get_cookie_no_session(self):
        """Test get_cookie returns None when no session."""
        client = HTTPClientAsync("TestService")

        result = client.get_cookie("CSRF-TOKEN")

        assert result is None

    async def test_get_cookie_with_session_no_cookie(self):
        """Test get_cookie returns None when cookie doesn't exist."""
        client = HTTPClientAsync("TestService")
        client.init()

        result = client.get_cookie("NON_EXISTENT")

        assert result is None

        # Cleanup
        await client.close()

    async def test_cookie_exists_with_session_cookie_present(self):
        """Test cookie_exists returns True when cookie exists."""
        client = HTTPClientAsync("TestService")
        client.init()

        # Manually add a cookie
        client.session.cookie_jar.update_cookies({"CSRF-TOKEN": "test_token"})

        result = client.cookie_exists("CSRF-TOKEN")

        assert result is True

        # Cleanup
        await client.close()

    async def test_get_cookie_returns_value(self):
        """Test get_cookie returns cookie value when exists."""
        client = HTTPClientAsync("TestService")
        client.init()

        # Manually add a cookie
        client.session.cookie_jar.update_cookies({"CSRF-TOKEN": "test_token_value"})

        result = client.get_cookie("CSRF-TOKEN")

        assert result == "test_token_value"

        # Cleanup
        await client.close()

    async def test_handle_response_success_json(self):
        """Test _handle_response returns JSON for successful response."""
        client = HTTPClientAsync("TestService")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = AsyncMock(return_value={"key": "value"})

        result = await client._handle_response(mock_response, expect_json=True)

        assert result == {"key": "value"}
        mock_response.json.assert_called_once()

    async def test_handle_response_success_text(self):
        """Test _handle_response returns text when expect_json=False."""
        client = HTTPClientAsync("TestService")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = AsyncMock(return_value="plain text response")

        result = await client._handle_response(mock_response, expect_json=False)

        assert result == "plain text response"
        mock_response.text.assert_called_once()

    async def test_handle_response_error(self):
        """Test _handle_response raises on HTTP error."""
        client = HTTPClientAsync("TestService")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
            )
        )

        with pytest.raises(aiohttp.ClientResponseError):
            await client._handle_response(mock_response)

    async def test_get_success(self):
        """Test _get method returns data on success."""
        client = HTTPClientAsync("TestService")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._get("http://test.com")

        assert result == {"data": "test"}

    async def test_get_connection_error_returns_none(self):
        """Test _get returns None on connection error."""
        client = HTTPClientAsync("TestService")

        mock_session = MagicMock()
        mock_session.get = MagicMock(
            side_effect=aiohttp.ClientConnectionError("Connection failed")
        )

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._get("http://test.com")

        assert result is None

    async def test_get_with_401_calls_login(self):
        """Test _get calls login callback on 401 response."""
        client = HTTPClientAsync("TestService")

        # First response: 401
        mock_response_401 = AsyncMock()
        mock_response_401.status = 401
        mock_response_401.__aenter__.return_value = mock_response_401
        mock_response_401.__aexit__.return_value = None

        # Second response: success
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.json = AsyncMock(return_value={"data": "success"})
        mock_response_200.__aenter__.return_value = mock_response_200
        mock_response_200.__aexit__.return_value = None
        mock_response_200.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get = MagicMock(
            side_effect=[mock_response_401, mock_response_200]
        )

        login_callback = AsyncMock()

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._get("http://test.com", login=login_callback)

        login_callback.assert_called_once()
        assert result == {"data": "success"}

    async def test_post_success_json(self):
        """Test _post method returns JSON data on success."""
        client = HTTPClientAsync("TestService")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"result": "ok"})
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._post(
                "http://test.com",
                json={"key": "value"},
            )

        assert result == {"result": "ok"}

    async def test_post_success_text(self):
        """Test _post method returns text when expect_json=False."""
        client = HTTPClientAsync("TestService")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="plain text")
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None
        mock_response.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_response)

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._post(
                "http://test.com",
                data={"key": "value"},
                expect_json=False,
            )

        assert result == "plain text"

    async def test_post_connection_error_returns_none(self):
        """Test _post returns None on connection error."""
        client = HTTPClientAsync("TestService")

        mock_session = MagicMock()
        mock_session.post = MagicMock(
            side_effect=aiohttp.ClientConnectionError("Connection failed")
        )

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._post("http://test.com", json={"key": "value"})

        assert result is None

    async def test_post_with_403_calls_login(self):
        """Test _post calls login callback on 403 response."""
        client = HTTPClientAsync("TestService")

        # First response: 403
        mock_response_403 = AsyncMock()
        mock_response_403.status = 403
        mock_response_403.__aenter__.return_value = mock_response_403
        mock_response_403.__aexit__.return_value = None

        # Second response: success
        mock_response_200 = AsyncMock()
        mock_response_200.status = 200
        mock_response_200.json = AsyncMock(return_value={"result": "success"})
        mock_response_200.__aenter__.return_value = mock_response_200
        mock_response_200.__aexit__.return_value = None
        mock_response_200.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.post = MagicMock(
            side_effect=[mock_response_403, mock_response_200]
        )

        login_callback = AsyncMock()

        with patch.object(client, "init"):
            client.session = mock_session
            result = await client._post(
                "http://test.com",
                json={"key": "value"},
                login=login_callback,
            )

        login_callback.assert_called_once()
        assert result == {"result": "success"}
