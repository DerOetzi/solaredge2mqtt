from requests.exceptions import HTTPError

from solaredge2mqtt.exceptions import ConfigurationException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import Forecast, ForecastAccount, ForecastAPIKeyInfo
from solaredge2mqtt.service.http import HTTPClient
from solaredge2mqtt.settings import ForecastSettings

LOCATION_PART = "/{latitude}/{longitude}"

API_KEY_INFO = "https://api.forecast.solar/{api_key}/info"

CHECK_URL = "https://api.forecast.solar/check" + LOCATION_PART
ESTIMATE_URL = "https://api.forecast.solar/{api_key}/estimate" + LOCATION_PART


class ForecastAPI(HTTPClient):
    def __init__(self, settings: ForecastSettings) -> None:
        super().__init__("Forecast API")
        self.settings = settings

        self.account = self.get_account()

        self._check_location()

    def get_account(self) -> ForecastAccount:
        account = ForecastAccount.PUBLIC
        if self.settings.api_key is not None:
            try:
                result = self._get(
                    API_KEY_INFO.format(
                        api_key=self.settings.api_key.get_secret_value()
                    )
                )
                api_key_info = ForecastAPIKeyInfo(**result["result"])
                account = api_key_info.account
            except HTTPError as error:
                raise ConfigurationException(
                    "Cannot get forecast account info"
                ) from error

        logger.info(
            "Forecast account: {account} (max. {account.allowed_strings} strings)",
            account=account,
        )

        if account.allowed_strings < 2 and self.settings.string2 is not None:
            raise ConfigurationException(
                "The configured API key does not support two strings."
            )

        return account

    def _check_location(self) -> None:
        try:
            result = self._get(
                CHECK_URL.format(
                    latitude=self.settings.latitude, longitude=self.settings.longitude
                )
            )

            logger.info(
                "Forecast configuration for location: {place}",
                place=result["result"]["place"],
            )
        except HTTPError as error:
            raise ConfigurationException(
                "Cannot check location for forecast"
            ) from error

    async def loop(self) -> Forecast | None:
        forecast = None

        try:
            result = self._get(
                self.estimate_url, headers={"Accept": "application/json"}
            )

            forecast = Forecast(**result["result"])
            logger.info(forecast)
        except HTTPError as error:
            logger.warning("Cannot get forecast: {error}", error=error)

        return forecast

    @property
    def estimate_url(self) -> str:
        estimate_url = ESTIMATE_URL.format(
            api_key=self.settings.api_key.get_secret_value(),
            latitude=self.settings.latitude,
            longitude=self.settings.longitude,
        )

        estimate_url += self.settings.string1.url_string

        if self.settings.string2 is not None:
            estimate_url += self.settings.string2.url_string

        return estimate_url
