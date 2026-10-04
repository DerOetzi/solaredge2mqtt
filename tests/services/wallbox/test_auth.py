"""Tests for wallbox __init__ module - AuthorizationTokens."""

import base64
import json
import time

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
        header = (
            base64.urlsafe_b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
            )
            .decode()
            .rstrip("=")
        )
        payload = (
            base64.urlsafe_b64encode(json.dumps({"exp": exp_time}).encode())
            .decode()
            .rstrip("=")
        )
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

    @staticmethod
    def _token_with_payload(payload: bytes) -> str:
        encoded = base64.urlsafe_b64encode(payload).decode().rstrip("=")
        return f"header.{encoded}.signature"

    @pytest.mark.parametrize(
        "token",
        [
            pytest.param("header.!!!.signature", id="invalid_base64"),
            pytest.param("header.YWJj.signature", id="non_json_payload"),
            pytest.param("header.gA.signature", id="non_utf8_payload"),
        ],
    )
    def test_get_exp_claim_undecodable_payload(self, token):
        """get_exp_claim raises InvalidDataException for undecodable payloads."""
        with pytest.raises(InvalidDataException) as exc_info:
            AuthorizationTokens.get_exp_claim(token)

        assert exc_info.value.message == "Cannot read token expiration"

    @pytest.mark.parametrize(
        "payload",
        [
            pytest.param({"sub": "user"}, id="missing_exp"),
            pytest.param({"exp": "soon"}, id="non_numeric_exp"),
            pytest.param({"exp": None}, id="null_exp"),
            pytest.param(["exp"], id="non_object_payload"),
        ],
    )
    def test_get_exp_claim_invalid_exp(self, payload):
        """get_exp_claim raises InvalidDataException for missing or invalid exp."""
        token = self._token_with_payload(json.dumps(payload).encode())

        with pytest.raises(InvalidDataException) as exc_info:
            AuthorizationTokens.get_exp_claim(token)

        assert exc_info.value.message == "Cannot read token expiration"

    @pytest.mark.parametrize(
        ("exp", "expected"),
        [
            pytest.param(1700000000.9, 1700000000, id="float_exp"),
            pytest.param("1700000000", 1700000000, id="numeric_string_exp"),
        ],
    )
    def test_get_exp_claim_coerces_exp_to_int(self, exp, expected):
        """get_exp_claim returns exp as int for numeric non-int values."""
        token = self._token_with_payload(json.dumps({"exp": exp}).encode())

        result = AuthorizationTokens.get_exp_claim(token)

        assert result == expected
        assert isinstance(result, int)

    def test_get_exp_claim_ignores_signature(self, valid_jwt_token):
        """get_exp_claim reads exp regardless of the signature segment."""
        token, exp_time = valid_jwt_token
        header, payload, _ = token.split(".")

        result = AuthorizationTokens.get_exp_claim(f"{header}.{payload}.tampered")

        assert result == exp_time

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

    def test_access_token_expires_raises_when_missing(self):
        """access_token_expires raises InvalidDataException if missing."""
        tokens = AuthorizationTokens(accessToken=None, refreshToken="abc")

        with pytest.raises(InvalidDataException) as exc_info:
            _ = tokens.access_token_expires

        assert exc_info.value.message == "Access token is missing"

    def test_refresh_token_expires_raises_when_missing(self):
        """refresh_token_expires raises InvalidDataException if missing."""
        tokens = AuthorizationTokens(accessToken="abc", refreshToken=None)

        with pytest.raises(InvalidDataException) as exc_info:
            _ = tokens.refresh_token_expires

        assert exc_info.value.message == "Refresh token is missing"
