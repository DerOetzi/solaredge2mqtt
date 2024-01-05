import time
from typing import Optional

import jwt
import urllib3
from pydantic import BaseModel, Field
from requests import get, post
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import WallboxAPI
from solaredge2mqtt.settings import ServiceSettings

urllib3.disable_warnings()

LOGIN_URL = "https://{host}:8443/v2/jwt/login"
REFRESH_URL = "https://{host}:8443/v2/jwt/refresh"
WALLBOX_URL = "https://{host}:8443/v2/wallboxes/{serial}"


class AuthorizationTokens(BaseModel):
    access_token: str = Field(None, alias="accessToken")
    refresh_token: str = Field(None, alias="refreshToken")

    @property
    def access_token_expires(self) -> int:
        payload = jwt.decode(self.access_token, options={"verify_signature": False})
        logger.debug("Access token expires at: {expires}", expires=payload["exp"])
        return payload["exp"]

    @property
    def refresh_token_expires(self) -> int:
        payload = jwt.decode(self.refresh_token, options={"verify_signature": False})
        logger.debug("Refresh token expires at: {expires}", expires=payload["exp"])
        return payload["exp"]


class WallboxClient:
    def __init__(self, settings: ServiceSettings):
        self.host = settings.wallbox_host
        self.password = settings.wallbox_password
        self.serial = settings.wallbox_serial

        logger.info(
            "Using Wallbox charger: {host}",
            host=settings.wallbox_host,
        )

        self.authorization: Optional[AuthorizationTokens] = None

    async def loop(self) -> WallboxAPI | None:
        wallbox = None

        try:
            self._get_access()

            response = get(
                WALLBOX_URL.format(host=self.host, serial=self.serial),
                headers={"Authorization": f"Bearer {self.authorization.access_token}"},
                timeout=5,
                verify=False,  # pylint: disable=insecure-request-warning
            )

            if response.status_code == 401:
                # Access token is invalid, login again (may happen after restart)
                self._login()
                wallbox = self.loop()
            else:
                response.raise_for_status()
                wallbox = WallboxAPI(response.json())
                logger.info(f"Wallbox: {wallbox.state}, {wallbox.power / 1000} kW", wallbox=wallbox)
        except HTTPError as error:
            logger.error(
                "Failed to get Wallbox data: {error}",
                error=error,
            )
        except RequestsConnectionError as error:
            logger.error(
                "Failed to connect to Wallbox charger: {error}",
                error=error,
            )
        except Timeout as error:
            logger.error(
                "Timeout while connecting to Wallbox charger: {error}",
                error=error,
            )

        return wallbox

    def _get_access(self) -> None:
        current_timestamp = int(time.time())

        try:
            if self.authorization is None:
                self._login()
            elif self.authorization.access_token_expires < current_timestamp + 60:
                # Token is about to expire within 60 seconds
                if self.authorization.refresh_token_expires < current_timestamp + 60:
                    # Refresh token is about to expire within 60 seconds as well new login
                    self._login()
                else:
                    self._refresh_token()
            else:
                logger.debug("Wallbox access token still valid")

        except HTTPError as error:
            logger.error(
                "Failed to get access token for wallbox charger: {error}",
                error=error,
            )
            raise error

    def _login(self):
        logger.info("Logging in to Wallbox charger...")
        self.authorization = None
        response = post(
            LOGIN_URL.format(host=self.host),
            json={"password": self.password, "username": "admin"},
            timeout=5,
            verify=False,  # pylint: disable=insecure-request-warning
        )
        response.raise_for_status()
        logger.trace(response.json())
        self.authorization = AuthorizationTokens(**response.json())
        logger.info("Logged in to EV charger")

    def _refresh_token(self):
        logger.info("Refreshing access token Wallbox...")
        response = post(
            REFRESH_URL.format(host=self.host),
            headers={"Authorization": f"Bearer {self.authorization.refresh_token}"},
            timeout=5,
            verify=False,  # pylint: disable=insecure-request-warning
        )

        if response.status_code == 401:
            # Refresh token is invalid, login again
            self._login()
        else:
            response.raise_for_status()
            payload = response.json()
            self.authorization.access_token = payload["accessToken"]

        logger.info("Refreshed access token Wallbox")
