from typing import Optional

from requests.exceptions import HTTPError

from solaredge2mqtt.exceptions import ConfigurationException
from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import (
    EnergyForecast,
    Forecast,
    ForecastAccount,
    ForecastAPIKeyInfo,
    ForecastPeriod,
)
from solaredge2mqtt.mqtt import MQTTClient
from solaredge2mqtt.persistence.influxdb import InfluxDB
from solaredge2mqtt.service.http import HTTPClient
from solaredge2mqtt.settings import ForecastSettings

LOCATION_PART = "/{latitude}/{longitude}"

API_KEY_INFO = "https://api.forecast.solar/{api_key}/info"

CHECK_URL = "https://api.forecast.solar/check" + LOCATION_PART
ESTIMATE_URL = "https://api.forecast.solar/{api_key}/estimate" + LOCATION_PART


class ForecastAPI(HTTPClient):

    def __init__(
        self,
        settings: ForecastSettings,
        mqtt: MQTTClient,
        influxdb: Optional[InfluxDB] = None,
    ) -> None:
        super().__init__("Forecast API")
        self.settings = settings

        self.mqtt = mqtt

        self.influxdb = influxdb

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
            logger.info("Read forecast from API")
            result = self._get(
                self.estimate_url, headers={"Accept": "application/json"}
            )

            forecast = Forecast(**result["result"])
            logger.debug(forecast.model_dump_json(indent=4))

            if self.influxdb:
                logger.info("Write forecast to influxdb")
                self.influxdb.write_points_to_aggregated_bucket(
                    forecast.influxdb_points
                )

                energy = self.read_from_influxdb()
                logger.info("Read forecast from influxdb: {energy}", energy=energy)
            else:
                energy = EnergyForecast.from_api(forecast)
                logger.info("Read forecast from API: {energy}", energy=energy)

            await self.mqtt.publish_to("forecast/energy", energy)

        except HTTPError as error:
            logger.warning("Cannot get forecast: {error}", error=error)

        return forecast

    def read_from_influxdb(self) -> EnergyForecast:
        energies = {}

        for period in ForecastPeriod:
            record = self.influxdb.query_timeunit(period, "forecast")
            if record is not None:
                energies[period.topic] = round(record.values["energy"], 3)
            else:
                energies[period.topic] = 0

        energy = EnergyForecast(**energies)
        return energy

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
