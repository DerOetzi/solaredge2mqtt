"""Tests for wallbox __init__ module - AuthorizationTokens."""

import base64
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import InvalidDataException
from solaredge2mqtt.services.wallbox import AuthorizationTokens


class TestAuthorizationTokens:
    """Tests for AuthorizationTokens class."""

    @pytest.fixture
    def valid_jwt_token(self):
        """Create a valid JWT token for testing."""
        # Create a simple JWT token (header.payload.signature)
        # Payload: {"exp": current_time + 3600} (expires in 1 hour)
        exp_time = int(time.time()) + 3600
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(
            json.dumps({"exp": exp_time}).encode()
        ).decode().rstrip("=")
        signature = base64.urlsafe_b64encode(b"fake_signature").decode().rstrip("=")

        return f"{header}.{payload}.{signature}", exp_time

    def test_authorization_tokens_creation(self, valid_jwt_token):
        """Test AuthorizationTokens creation."""
        token, _ = valid_jwt_token

        tokens = AuthorizationTokens(
            accessToken=token,
            refreshToken=token,
        )

        assert tokens.access_token == token
        assert tokens.refresh_token == token

    def test_access_token_expires(self, valid_jwt_token):
        """Test access_token_expires property."""
        token, exp_time = valid_jwt_token

        tokens = AuthorizationTokens(
            accessToken=token,
            refreshToken=token,
        )

        assert tokens.access_token_expires == exp_time

    def test_refresh_token_expires(self, valid_jwt_token):
        """Test refresh_token_expires property."""
        token, exp_time = valid_jwt_token

        tokens = AuthorizationTokens(
            accessToken=token,
            refreshToken=token,
        )

        assert tokens.refresh_token_expires == exp_time

    def test_get_exp_claim_invalid_token(self):
        """Test get_exp_claim raises exception for invalid token."""
        with pytest.raises(InvalidDataException) as exc_info:
            AuthorizationTokens.get_exp_claim("invalid_token")

        assert exc_info.value.message == "Cannot read token expiration"

    def test_get_exp_claim_valid_token(self, valid_jwt_token):
        """Test get_exp_claim returns exp for valid token."""
        token, exp_time = valid_jwt_token

        result = AuthorizationTokens.get_exp_claim(token)

        assert result == exp_time

    def test_authorization_tokens_none_values(self):
        """Test AuthorizationTokens with None values."""
        tokens = AuthorizationTokens()

        assert tokens.access_token is None
        assert tokens.refresh_token is None
