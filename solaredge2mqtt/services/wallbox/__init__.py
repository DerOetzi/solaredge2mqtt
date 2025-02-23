import asyncio
import time

import aiohttp
import jwt
from aiohttp.client_exceptions import ClientResponseError
from pydantic import BaseModel, Field

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.http_async import HTTPClientAsync
from solaredge2mqtt.services.wallbox.events import WallboxReadEvent
from solaredge2mqtt.services.wallbox.models import WallboxAPI
from solaredge2mqtt.services.wallbox.settings import WallboxSettings

LOGIN_URL = "https://{host}:8443/v2/jwt/login"
REFRESH_URL = "https://{host}:8443/v2/jwt/refresh"
WALLBOX_URL = "https://{host}:8443/v2/wallboxes/{serial}"


class AuthorizationTokens(BaseModel):
    access_token: str | None = Field(None, alias="accessToken")
    refresh_token: str | None = Field(None, alias="refreshToken")

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


class WallboxClient(HTTPClientAsync):
    def __init__(self, settings: WallboxSettings, event_bus: EventBus):
        super().__init__("Wallbox API")
        self.settings = settings
        self.event_bus = event_bus
        self.authorization: AuthorizationTokens | None = None

        logger.info(
            "Using Wallbox charger: {host}",
            host=settings.host,
        )

    async def get_data(self) -> WallboxAPI | None:
        wallbox = None
        try:
            await self._get_access()

            response = await self._get(
                WALLBOX_URL.format(
                    host=self.settings.host, serial=self.settings.serial
                ),
                headers={"Authorization": f"Bearer {self.authorization.access_token}"},
                verify=False,
                login=self.login,
            )

            if response is None:
                raise InvalidDataException("Invalid Wallbox data")

            wallbox = WallboxAPI(response)
            logger.info(
                f"Wallbox: {wallbox.state}, {wallbox.power / 1000} kW",
                wallbox=wallbox,
            )

            await self.event_bus.emit(WallboxReadEvent(wallbox))
        except ClientResponseError as error:
            raise InvalidDataException(f"Cannot read Wallbox data: {error}") from error

        return wallbox

    async def _get_access(self) -> None:
        current_timestamp = int(time.time())

        if self.authorization is None:
            await self.login()
        elif self.authorization.access_token_expires < current_timestamp + 60:
            if self.authorization.refresh_token_expires < current_timestamp + 60:
                await self.login()
            else:
                await self._refresh_token()
        else:
            logger.debug("Wallbox access token still valid")

    async def login(self):
        try:
            logger.info("Logging in to Wallbox charger...")
            self.authorization = None
            response = await self._post(
                LOGIN_URL.format(host=self.settings.host),
                json={
                    "password": self.settings.password.get_secret_value(),
                    "username": "admin",
                },
                verify=False,
            )

            if response is None:
                raise ConfigurationException("wallbox", "Invalid Wallbox login")

            self.authorization = AuthorizationTokens(**response)
            logger.info("Logged in to EV charger")
        except ClientResponseError as error:
            raise ConfigurationException(
                "wallbox", "Unable to login to EV charger"
            ) from error

    async def _refresh_token(self):
        logger.info("Refreshing access token Wallbox...")
        response = await self._post(
            REFRESH_URL.format(host=self.settings.host),
            headers={"Authorization": f"Bearer {self.authorization.refresh_token}"},
            verify=False,
            login=self.login,
        )

        self.authorization.access_token = response["accessToken"]
        logger.info("Refreshed access token Wallbox")
