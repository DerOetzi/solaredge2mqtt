import json

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import Forecast, ForecastAPIKeyInfo, ForecastAccount
from solaredge2mqtt.settings import ForecastSettings

LOCATION_PART = "/{latitude}/{longitude}"

API_KEY_INFO = "https://api.forecast.solar/{api_key}/info"

CHECK_URL = "https://api.forecast.solar/check" + LOCATION_PART
ESTIMATE_URL = "https://api.forecast.solar/{api_key}/estimate" + LOCATION_PART


class ForecastAPI:
    def __init__(self, settings: ForecastSettings) -> None:
        self.settings = settings

        self.session = requests.session()

        self.account = self.get_account()
        self._check_location()

    def get_account(self) -> ForecastAccount:
        account = ForecastAccount.PUBLIC
        try:
            if self.settings.api_key is not None:
                response = self.session.get(
                    API_KEY_INFO.format(api_key=self.settings.api_key)
                )

                response.raise_for_status()

                result = json.loads(response.content.decode("utf-8"))
                api_key_info = ForecastAPIKeyInfo(**result["result"])
                account = api_key_info.account

            logger.info(
                "Forecast account: {account} (max. {account.allowed_strings} strings)",
                account=account,
            )

            if account.allowed_strings < 2 and self.settings.string2 is not None:
                logger.error("The configured API key does not support two strings.")

        except HTTPError as error:
            logger.error("Cannot validate Forecast configuration: {error}", error=error)

        return account

    def _check_location(self) -> None:
        response = self.session.get(
            CHECK_URL.format(
                latitude=self.settings.latitude, longitude=self.settings.longitude
            )
        )

        if response.status_code == 200:
            result = json.loads(response.content.decode("utf-8"))
            logger.info(
                "Forecast configuration for place: {place}",
                place=result["result"]["place"],
            )
        else:
            raise HTTPError(
                f"Cannot validate Forecast configured location (status code: {response.status_code})"
            )

    async def loop(self) -> Forecast | None:
        forecast = None

        try:
            response = self.session.get(
                self.estimate_url, headers={"Accept": "application/json"}
            )

            response.raise_for_status()
            result = json.loads(response.content.decode("utf-8"))
            forecast = Forecast(**result["result"])
        except HTTPError as error:
            logger.error("Cannot get forecast: {error}", error=error)
        except RequestsConnectionError as error:
            logger.error(
                "Failed to connect to forecast API: {error}",
                error=error,
            )
        except Timeout as error:
            logger.error(
                "Timeout while connecting to forecast API: {error}",
                error=error,
            )

        return forecast

    @property
    def estimate_url(self) -> str:
        estimate_url = ESTIMATE_URL.format(
            api_key=self.settings.api_key,
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
        )

        estimate_url += self.settings.string1.url_string

        if self.settings.string2 is not None:
            estimate_url += self.settings.string2.url_string

        return estimate_url
