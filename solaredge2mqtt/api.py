import json
from typing import Optional

import requests
from requests.exceptions import HTTPError, RequestException

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import (
    LogicalInfo,
    LogicalInverter,
    LogicalModule,
    LogicalString,
)
from solaredge2mqtt.settings import ServiceSettings

LOGIN_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/login"
LOGICAL_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/sites/{site_id}/layout/logical"


class MonitoringSite:
    def __init__(self, settings: ServiceSettings) -> None:
        self.username = settings.api_username
        self.password = settings.api_password
        self.site_id = settings.api_site_id

        self.session = requests.session()

    def login(self) -> None:
        result = self.session.post(
            LOGIN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"j_username": self.username, "j_password": self.password},
        )

        if result.status_code == 200:
            logger.info("Login to monitoring site successful")
        else:
            raise HTTPError(
                f"Cannot login to monitoring site (status code: {result.status_code})"
            )

    def get_module_energies(self) -> list[LogicalInverter] | None:
        modules = None
        try:
            logical = self._get_logical()

            logger.debug("Logical: {logical}", logical=json.dumps(logical, indent=4))

            inverters = self._parse_inverters(
                logical["logicalTree"]["children"], logical["reportersData"]
            )

            modules = []

            for inverter in inverters:
                logger.debug(
                    "Inverter: {inverter}", inverter=inverter.model_dump_json(indent=4)
                )
                for string in inverter.strings:
                    for module in string.modules:
                        modules.append(module)
        except RequestException as error:
            logger.error(
                "Exception while reading data from monitoring site: {exception}",
                exception=error,
            )

        return modules

    def _get_logical(self, run: Optional[int] = 0) -> dict:
        result = self.session.get(
            LOGICAL_URL.format(site_id=self.site_id),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-CSRF-TOKEN": self.session.cookies["CSRF-TOKEN"],
            },
        )

        if result.status_code == 200:
            return json.loads(result.content.decode("utf-8"))
        elif result.status_code in (401, 403) and run == 0:
            logger.info("Login expired, logging in again")
            self.login()
            logger.info("Retrying to get logical layout")
            return self._get_logical(run=1)

        raise HTTPError(
            f"Cannot read logical layout (status code: {result.status_code})"
        )

    def _parse_inverters(self, inverter_objs, reporters_data) -> list[LogicalInverter]:
        inverters = []

        for inverter_obj in inverter_objs:
            info = LogicalInfo.map(inverter_obj["data"])
            if "INVERTER" in info["type"]:
                inverter = LogicalInverter(
                    info=info,
                    energy=reporters_data[info["id"]]["unscaledEnergy"]
                    if info["id"] in reporters_data
                    else None,
                )

                self._parse_strings(inverter, inverter_obj["children"], reporters_data)

                inverters.append(inverter)

            else:
                logger.info("Unknown inverter type: {type}", type=info["type"])

        return inverters

    def _parse_strings(self, inverter, string_objs, reporters_data):
        for string_obj in string_objs:
            info = LogicalInfo.map(string_obj["data"])
            string = LogicalString(
                info=info,
                energy=reporters_data[info["id"]]["unscaledEnergy"]
                if info["id"] in reporters_data
                else None,
            )

            self._parse_panels(string, string_obj["children"], reporters_data)

            inverter.strings.append(string)

    def _parse_panels(self, string, panel_objs, reporters_data):
        for panel_obj in panel_objs:
            info = LogicalInfo.map(panel_obj["data"])
            panel = LogicalModule(
                info=info,
                energy=reporters_data[info["id"]]["unscaledEnergy"]
                if info["id"] in reporters_data
                else None,
            )

            string.modules.append(panel)
