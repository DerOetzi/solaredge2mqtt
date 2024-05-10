from requests.exceptions import HTTPError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent
from solaredge2mqtt.services.http import HTTPClient
from solaredge2mqtt.services.monitoring.models import (
    LogicalInfo,
    LogicalInverter,
    LogicalModule,
    LogicalString,
)
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings

LOGIN_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/login"
LOGICAL_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/sites/{site_id}/layout/logical"


class MonitoringSite(HTTPClient):
    def __init__(self, settings: MonitoringSettings, event_bus: EventBus) -> None:
        super().__init__("Monitoring Site")
        self.settings = settings

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(Interval10MinTriggerEvent, self.get_data)

    async def get_data(self, _):
        modules = self.get_module_energies()

        if modules is None:
            logger.warning("Invalid monitoring data, skipping this loop")
            return

        energy_total = 0
        count_modules = 0
        for module in modules:
            if module.energy is not None:
                count_modules += 1
                energy_total += module.energy

        logger.info(
            "Read from monitoring total energy: {energy_total} kWh from {count_modules} modules",
            energy_total=energy_total / 1000,
            count_modules=count_modules,
        )

        await self.event_bus.emit(
            MQTTPublishEvent("monitoring/pv_energy_today", energy_total)
        )

        for module in modules:
            await self.event_bus.emit(
                MQTTPublishEvent(
                    f"monitoring/module/{module.info.serialnumber}",
                    module,
                )
            )

    def login(self) -> None:
        try:
            self._post(
                LOGIN_URL,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "j_username": self.settings.username,
                    "j_password": self.settings.password.get_secret_value(),
                },
                timeout=10,
                expect_json=False,
            )

            logger.info("Login to monitoring site successful")
        except HTTPError as error:
            raise ConfigurationException(
                "Monitoring", "Unable to login to monitoring account"
            ) from error

    def get_module_energies(self) -> list[LogicalInverter] | None:
        modules = None
        logical = self._get_logical()

        if logical is None:
            raise InvalidDataException(
                "Unable to read logical layout from monitoring site"
            )

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

        return modules

    def _get_logical(self) -> dict | None:
        result = None
        try:
            if "CSRF-TOKEN" not in self.session.cookies:
                self.login()

            result = self._get(
                LOGICAL_URL.format(site_id=self.settings.site_id),
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRF-TOKEN": self.session.cookies["CSRF-TOKEN"],
                },
                timeout=10,
            )
        except HTTPError as error:
            raise InvalidDataException("Unable to read logical layout") from error

        return result

    def _parse_inverters(self, inverter_objs, reporters_data) -> list[LogicalInverter]:
        inverters = []

        for inverter_obj in inverter_objs:
            info = LogicalInfo.map(inverter_obj["data"])
            if "INVERTER" in info["type"]:
                inverter = LogicalInverter(
                    info=info,
                    energy=(
                        reporters_data[info["id"]]["unscaledEnergy"]
                        if info["id"] in reporters_data
                        else None
                    ),
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
                energy=(
                    reporters_data[info["id"]]["unscaledEnergy"]
                    if info["id"] in reporters_data
                    else None
                ),
            )

            self._parse_panels(string, string_obj["children"], reporters_data)

            inverter.strings.append(string)

    def _parse_panels(self, string, panel_objs, reporters_data):
        for panel_obj in panel_objs:
            info = LogicalInfo.map(panel_obj["data"])
            panel = LogicalModule(
                info=info,
                energy=(
                    reporters_data[info["id"]]["unscaledEnergy"]
                    if info["id"] in reporters_data
                    else None
                ),
            )

            string.modules.append(panel)
