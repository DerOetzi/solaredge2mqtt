import base64
import hashlib
import html
import re
import secrets
import time
from urllib.parse import parse_qs, urlparse

import aiohttp

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings

COGNITO_DOMAIN = "https://login.solaredge.com"
COGNITO_CLIENT_ID = "ugfnsujd3384sshcjehaphlh3"
COGNITO_LOGIN_URL = f"{COGNITO_DOMAIN}/login"
COGNITO_TOKEN_URL = f"{COGNITO_DOMAIN}/oauth2/token"
REDIRECT_URI = "https://monitoring.solaredge.com/mfe/auth/callback"
TOKEN_REFRESH_MARGIN_SECONDS = 300

CSRF_PATTERN = re.compile(r'name="csrf"\s+value="([^"]+)"')


class MonitoringAuth:
    def __init__(self, settings: MonitoringSettings) -> None:
        self.settings = settings
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0

    def invalidate(self) -> None:
        self._access_token = None
        self._expires_at = 0.0

    async def access_token(self, session: aiohttp.ClientSession) -> str:
        if self._access_token and time.monotonic() < self._expires_at:
            return self._access_token

        if self._refresh_token and await self._refresh(session):
            logger.debug("Refreshed monitoring access token")
        else:
            await self._login(session)
            logger.info("Login to monitoring site successful")

        if self._access_token is None:
            raise ConfigurationException(
                "Monitoring", "Login to monitoring account failed."
            )

        return self._access_token

    async def _login(self, session: aiohttp.ClientSession) -> None:
        verifier, challenge = self._pkce_pair()
        params = {
            "lang": "en",
            "response_type": "code",
            "client_id": COGNITO_CLIENT_ID,
            "scope": "email openid",
            "redirect_uri": REDIRECT_URI,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }

        async with session.get(COGNITO_LOGIN_URL, params=params) as response:
            response.raise_for_status()
            page = await response.text()

        match = CSRF_PATTERN.search(page)
        if match is None:
            raise ConfigurationException(
                "Monitoring", "Unexpected monitoring login page format."
            )

        async with session.post(
            COGNITO_LOGIN_URL,
            params=params,
            data={
                "username": self.settings.username_value,
                "password": self.settings.password_secret,
                "csrf": html.unescape(match.group(1)),
                "cognitoAsfData": "",
            },
            allow_redirects=False,
        ) as response:
            location = response.headers.get("Location", "")
            status = response.status

        code = self._extract_code(status, location)

        await self._request_tokens(
            session,
            {
                "grant_type": "authorization_code",
                "client_id": COGNITO_CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "code": code,
                "code_verifier": verifier,
            },
        )

    async def _refresh(self, session: aiohttp.ClientSession) -> bool:
        try:
            await self._request_tokens(
                session,
                {
                    "grant_type": "refresh_token",
                    "client_id": COGNITO_CLIENT_ID,
                    "refresh_token": self._refresh_token or "",
                },
            )
            return True
        except aiohttp.ClientResponseError as error:
            logger.debug("Monitoring token refresh failed: {error}", error=error)
            self._refresh_token = None
            return False

    async def _request_tokens(
        self, session: aiohttp.ClientSession, data: dict[str, str]
    ) -> None:
        async with session.post(COGNITO_TOKEN_URL, data=data) as response:
            response.raise_for_status()
            tokens = await response.json()

        access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
        if not isinstance(access_token, str) or not access_token:
            raise ConfigurationException(
                "Monitoring", "Monitoring login returned no access token."
            )

        expires_in = tokens.get("expires_in", 3600)
        if not isinstance(expires_in, int | float):
            expires_in = 3600

        self._access_token = access_token
        self._expires_at = (
            time.monotonic() + float(expires_in) - TOKEN_REFRESH_MARGIN_SECONDS
        )

        refresh_token = tokens.get("refresh_token")
        if isinstance(refresh_token, str) and refresh_token:
            self._refresh_token = refresh_token

    @staticmethod
    def _extract_code(status: int, location: str) -> str:
        if status not in (301, 302, 303) or not location.startswith(REDIRECT_URI):
            raise ConfigurationException(
                "Monitoring",
                "Login to monitoring account failed. "
                "Check username and password; multi-factor authentication "
                "is not supported.",
            )

        codes = parse_qs(urlparse(location).query).get("code")
        if not codes:
            raise ConfigurationException(
                "Monitoring", "Monitoring login returned no authorization code."
            )

        return codes[0]

    @staticmethod
    def _pkce_pair() -> tuple[str, str]:
        verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return verifier, challenge
