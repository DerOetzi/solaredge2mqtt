import base64
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import aiohttp
import pytest
from aiohttp import ClientResponseError, RequestInfo
from pydantic import SecretStr

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.services.monitoring.auth import (
    COGNITO_CLIENT_ID,
    COGNITO_LOGIN_URL,
    COGNITO_TOKEN_URL,
    REDIRECT_URI,
    TOKEN_REFRESH_MARGIN_SECONDS,
    MonitoringAuth,
)
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings

LOGIN_PAGE = '<form><input type="hidden" name="csrf" value="abc&#x2F;def="/></form>'
CALLBACK = f"{REDIRECT_URI}?code=the-code"


def _response(
    status: int = 200,
    text: str = "",
    json_data: object = None,
    headers: dict[str, str] | None = None,
    error: bool = False,
) -> MagicMock:
    response = MagicMock()
    response.status = status
    response.headers = headers or {}
    response.text = AsyncMock(return_value=text)
    response.json = AsyncMock(return_value=json_data)
    if error:
        response.raise_for_status = MagicMock(
            side_effect=ClientResponseError(
                request_info=MagicMock(spec=RequestInfo), history=(), status=status
            )
        )
    else:
        response.raise_for_status = MagicMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


def _tokens(
    access: str = "access",
    refresh: str | None = "refresh",
    expires: object = 86400,
) -> dict[str, object]:
    tokens: dict[str, object] = {"access_token": access, "expires_in": expires}
    if refresh is not None:
        tokens["refresh_token"] = refresh
    return tokens


@pytest.fixture
def settings() -> MonitoringSettings:
    return MonitoringSettings(
        site_id=SecretStr("12345"),
        username="user@example.com",
        password=SecretStr("secret"),
    )


@pytest.fixture
def session() -> MagicMock:
    return MagicMock(spec=aiohttp.ClientSession)


def _login_session(session: MagicMock, tokens: object, post_status: int = 302) -> None:
    session.get = MagicMock(return_value=_response(text=LOGIN_PAGE))
    session.post = MagicMock(
        side_effect=[
            _response(status=post_status, headers={"Location": CALLBACK}),
            _response(json_data=tokens),
        ]
    )


class TestMonitoringAuthLogin:
    async def test_login_runs_pkce_code_flow(self, settings, session):
        _login_session(session, _tokens())
        auth = MonitoringAuth(settings)

        token = await auth.access_token(session)

        assert token == "access"
        get_call = session.get.call_args
        assert get_call.args[0] == COGNITO_LOGIN_URL
        params = get_call.kwargs["params"]
        assert params["client_id"] == COGNITO_CLIENT_ID
        assert params["redirect_uri"] == REDIRECT_URI
        assert params["code_challenge_method"] == "S256"

        form_call, token_call = session.post.call_args_list
        assert form_call.args[0] == COGNITO_LOGIN_URL
        assert form_call.kwargs["allow_redirects"] is False
        assert form_call.kwargs["data"] == {
            "username": "user@example.com",
            "password": "secret",
            "csrf": "abc/def=",
            "cognitoAsfData": "",
        }

        assert token_call.args[0] == COGNITO_TOKEN_URL
        token_data = token_call.kwargs["data"]
        assert token_data["grant_type"] == "authorization_code"
        assert token_data["code"] == "the-code"
        verifier = token_data["code_verifier"]
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        assert params["code_challenge"] == expected

    async def test_cached_token_is_reused(self, settings, session):
        _login_session(session, _tokens())
        auth = MonitoringAuth(settings)

        await auth.access_token(session)
        token = await auth.access_token(session)

        assert token == "access"
        assert session.get.call_count == 1
        assert session.post.call_count == 2

    async def test_login_page_without_csrf_raises(self, settings, session):
        session.get = MagicMock(return_value=_response(text="<html></html>"))
        auth = MonitoringAuth(settings)

        with pytest.raises(ConfigurationException):
            await auth.access_token(session)

    async def test_login_page_http_error_propagates(self, settings, session):
        session.get = MagicMock(return_value=_response(status=503, error=True))
        auth = MonitoringAuth(settings)

        with pytest.raises(ClientResponseError):
            await auth.access_token(session)

    async def test_rejected_credentials_raise(self, settings, session):
        session.get = MagicMock(return_value=_response(text=LOGIN_PAGE))
        session.post = MagicMock(return_value=_response(status=200))
        auth = MonitoringAuth(settings)

        with pytest.raises(ConfigurationException, match="Check username"):
            await auth.access_token(session)

    async def test_redirect_to_other_target_raises(self, settings, session):
        session.get = MagicMock(return_value=_response(text=LOGIN_PAGE))
        session.post = MagicMock(
            return_value=_response(
                status=302, headers={"Location": "https://login.solaredge.com/mfa"}
            )
        )
        auth = MonitoringAuth(settings)

        with pytest.raises(ConfigurationException, match="Check username"):
            await auth.access_token(session)

    async def test_redirect_without_code_raises(self, settings, session):
        session.get = MagicMock(return_value=_response(text=LOGIN_PAGE))
        session.post = MagicMock(
            return_value=_response(
                status=302, headers={"Location": f"{REDIRECT_URI}?error=denied"}
            )
        )
        auth = MonitoringAuth(settings)

        with pytest.raises(ConfigurationException, match="authorization code"):
            await auth.access_token(session)

    @pytest.mark.parametrize("tokens", [{}, {"access_token": ""}, ["x"]])
    async def test_token_response_without_access_token_raises(
        self, settings, session, tokens
    ):
        _login_session(session, tokens)
        auth = MonitoringAuth(settings)

        with pytest.raises(ConfigurationException, match="no access token"):
            await auth.access_token(session)

    async def test_invalid_expires_in_falls_back(self, settings, session):
        _login_session(session, _tokens(expires="soon"))
        auth = MonitoringAuth(settings)

        with patch(
            "solaredge2mqtt.services.monitoring.auth.time.monotonic", return_value=0.0
        ):
            await auth.access_token(session)

        assert auth._expires_at == 3600 - TOKEN_REFRESH_MARGIN_SECONDS


class TestMonitoringAuthRefresh:
    async def test_expired_token_is_refreshed(self, settings, session):
        _login_session(session, _tokens())
        auth = MonitoringAuth(settings)
        await auth.access_token(session)

        session.post = MagicMock(
            return_value=_response(json_data=_tokens(access="new", refresh=None))
        )
        auth._expires_at = 0.0

        token = await auth.access_token(session)

        assert token == "new"
        data = session.post.call_args.kwargs["data"]
        assert data == {
            "grant_type": "refresh_token",
            "client_id": COGNITO_CLIENT_ID,
            "refresh_token": "refresh",
        }
        assert auth._refresh_token == "refresh"
        assert session.get.call_count == 1

    async def test_failed_refresh_falls_back_to_login(self, settings, session):
        _login_session(session, _tokens())
        auth = MonitoringAuth(settings)
        await auth.access_token(session)
        auth.invalidate()

        session.post = MagicMock(
            side_effect=[
                _response(status=400, error=True),
                _response(status=302, headers={"Location": CALLBACK}),
                _response(json_data=_tokens(access="fresh", refresh="refresh2")),
            ]
        )

        token = await auth.access_token(session)

        assert token == "fresh"
        assert auth._refresh_token == "refresh2"
        assert session.get.call_count == 2

    async def test_login_without_refresh_token_forces_login_next_time(
        self, settings, session
    ):
        _login_session(session, _tokens(refresh=None))
        auth = MonitoringAuth(settings)
        await auth.access_token(session)
        auth.invalidate()

        _login_session(session, _tokens(access="second"))

        assert await auth.access_token(session) == "second"

    async def test_missing_token_after_flow_raises(self, settings, session):
        auth = MonitoringAuth(settings)
        auth._login = AsyncMock()

        with pytest.raises(ConfigurationException, match="Login to monitoring"):
            await auth.access_token(session)


class TestPkce:
    def test_pkce_pair_is_valid(self):
        verifier, challenge = MonitoringAuth._pkce_pair()

        assert 43 <= len(verifier) <= 128
        digest = hashlib.sha256(verifier.encode()).digest()
        assert challenge == base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    def test_extract_code_accepts_303(self):
        assert MonitoringAuth._extract_code(303, CALLBACK) == "the-code"
        assert parse_qs(urlparse(CALLBACK).query)["code"] == ["the-code"]
