from typing import Optional

import requests
import urllib3
from pydantic import BaseModel, Field

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import WallboxAPI
from solaredge2mqtt.settings import ServiceSettings

urllib3.disable_warnings()

LOGIN_URL = "https://{host}:8443/v2/jwt/login"
WALLBOX_URL = "https://{host}:8443/v2/wallboxes/{serial}"


class AuthorizationTokens(BaseModel):
    access_token: str = Field(None, alias="accessToken")
    refresh_token: str = Field(None, alias="refreshToken")


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

    def loop(self) -> WallboxAPI:
        self._login()

        response = requests.get(
            WALLBOX_URL.format(host=self.host, serial=self.serial),
            headers={"Authorization": f"Bearer {self.authorization.access_token}"},
            timeout=5,
            verify=False,
        )

        if response.status_code == 401:
            logger.info("Refreshing authorization token Wallbox...")
            self.authorization = None
            self._login()

            wallbox = self.loop()
        else:
            response.raise_for_status()
            wallbox = WallboxAPI(response.json())
            logger.info(f"Wallbox: {wallbox}", wallbox=wallbox)

        return wallbox

    def _login(self) -> None:
        if self.authorization is None:
            logger.info("Logging in to Wallbox charger...")

            response = requests.post(
                LOGIN_URL.format(host=self.host),
                json={"password": self.password, "username": "admin"},
                timeout=5,
                verify=False,
            )
            response.raise_for_status()

            logger.trace(response.json())
            self.authorization = AuthorizationTokens(**response.json())

            logger.info("Logged in to EV charger")
