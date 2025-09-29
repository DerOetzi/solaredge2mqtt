import asyncio
import json
from datetime import datetime, timezone

from aiohttp import ClientResponseError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync, Point
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import Interval15MinTriggerEvent
from solaredge2mqtt.services.http_async import HTTPClientAsync
from solaredge2mqtt.services.monitoring.models import (
    LogicalInfo,
    LogicalInverter,
    LogicalModule,
    LogicalString,
)
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings

LOGIN_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/login"
LOGICAL_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/sites/{site_id}/layout/logical"
POWER_PUBLIC_URL = "https://monitoring.solaredge.com/solaredge-web/p/playbackData"
CONTENT_TYPE_FORM_URLENCODED = "application/x-www-form-urlencoded"


class MonitoringSite(HTTPClientAsync):
    def __init__(
        self,
        settings: MonitoringSettings,
        event_bus: EventBus,
        influxdb: InfluxDBAsync | None,
    ) -> None:
        super().__init__("Monitoring Site")
        self.settings = settings

        self.influxdb: InfluxDBAsync | None = influxdb

        self.event_bus = event_bus
        self._subscribe_events()

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(Interval15MinTriggerEvent, self.get_data)

    async def get_data(self, _):
        energies = await self.get_modules_energy()
        powers = await self.get_modules_power()

        modules = self.merge_modules(energies, powers)

        energy_total = 0
        count_modules = 0

        await self.save_to_influxdb(modules)
        await self.publish_mqtt(modules, energy_total, count_modules)

    async def get_modules_energy(self) -> dict[str, LogicalModule]:
        logical = await self._get_logical()

        if logical is None:
            raise InvalidDataException(
                "Unable to read logical layout from monitoring site"
            )

        inverters = self._parse_inverters(
            logical["logicalTree"]["children"], logical["reportersData"]
        )

        modules = {}

        for inverter in inverters:
            logger.debug(
                "Inverter: {inverter}", inverter=inverter.model_dump_json(indent=4)
            )
            for string in inverter.strings:
                for module in string.modules:
                    modules[module.info.identifier] = module

        return modules

    async def _get_logical(self) -> dict | None:
        result = None
        try:
            if not self.cookie_exists("CSRF-TOKEN"):
                await self.login()

            async with asyncio.timeout(10):
                result = await self._get(
                    LOGICAL_URL.format(site_id=self.settings.site_id),
                    headers={
                        "Content-Type": CONTENT_TYPE_FORM_URLENCODED,
                        "X-CSRF-TOKEN": self.get_cookie("CSRF-TOKEN"),
                    }
                )
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise InvalidDataException(
                "Unable to read logical layout") from error

        return result

    def _parse_inverters(self, inverter_objs, reporters_data) -> list[LogicalInverter]:
        inverters = []

        for inverter_obj in inverter_objs:
            info = LogicalInfo.map(inverter_obj["data"])
            if "INVERTER" in info["type"]:
                inverter = LogicalInverter(
                    info=info,
                    energy=(
                        reporters_data[info["identifier"]]["unscaledEnergy"]
                        if info["identifier"] in reporters_data
                        else None
                    ),
                )

                self._parse_strings(
                    inverter, inverter_obj["children"], reporters_data)

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
                    reporters_data[info["identifier"]]["unscaledEnergy"]
                    if info["identifier"] in reporters_data
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
                    reporters_data[info["identifier"]]["unscaledEnergy"]
                    if info["identifier"] in reporters_data
                    else None
                ),
            )

            string.modules.append(panel)

    async def get_modules_power(self) -> dict[str, dict[datetime, float]]:
        playback = await self._get_playback()

        if playback is None:
            raise InvalidDataException(
                "Unable to read playback data from monitoring site"
            )

        modules = {}

        for date_str, reporters_data in playback["reportersData"].items():
            date = datetime.strptime(
                date_str, "%a %b %d %H:%M:%S GMT %Y").astimezone()

            for entries in reporters_data.values():
                for entry in entries:
                    key = entry["key"]
                    if key not in modules:
                        modules[key] = {}

                    modules[key][date] = float(entry["value"])

        logger.debug(modules)

        return modules

    async def _get_playback(self) -> dict | None:
        result = None
        try:
            if not self.cookie_exists("CSRF-TOKEN"):
                await self.login()
            async with asyncio.timeout(10):
                playback_data = await self._post(
                    POWER_PUBLIC_URL,
                    data={
                        "fieldId": self.settings.site_id,
                        "timeUnit": 4,
                        "CSRF": self.get_cookie("CSRF-TOKEN"),
                    },
                    headers={
                        "Content-Type": CONTENT_TYPE_FORM_URLENCODED,
                        "X-CSRF-TOKEN": self.get_cookie("CSRF-TOKEN"),
                    },
                    expect_json=False,
                )

            response = (
                playback_data.replace("'", '"')
                .replace("Array", "")
                .replace("key", '"key"')
                .replace("value", '"value"')
                .replace("timeUnit", '"timeUnit"')
                .replace("fieldData", '"fieldData"')
                .replace("reportersData", '"reportersData"')
            )

            result = json.loads(response)
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise InvalidDataException(
                "Unable to read logical layout") from error

        return result

    async def login(self) -> None:
        try:
            async with asyncio.timeout(10):
                await self._post(
                    LOGIN_URL,
                    headers={"Content-Type": CONTENT_TYPE_FORM_URLENCODED},
                    data={
                        "j_username": self.settings.username,
                        "j_password": self.settings.password.get_secret_value(),
                    },
                    expect_json=False,
                )

            logger.info("Login to monitoring site successful")
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise ConfigurationException(
                "Monitoring", "Unable to login to monitoring account"
            ) from error

    @staticmethod
    def merge_modules(
        energies: dict[str, LogicalModule], powers: dict[str, dict[datetime, float]]
    ) -> dict[str, LogicalModule]:
        modules = {}

        for sid, module in energies.items():
            if sid in powers:
                module.power = powers[sid]

            modules[sid] = module

        return modules

    async def save_to_influxdb(self, modules):
        if self.influxdb is not None:
            points = []
            for module in modules.values():
                if module.power is not None:
                    for date, module_power in module.power.items():
                        point = Point("modules")
                        point.field("power", module_power)
                        point.time(date.astimezone(timezone.utc))
                        point.tag("serialnumber", module.info.serialnumber)
                        point.tag("name", module.info.name)
                        point.tag("identifier", module.info.identifier)
                        points.append(point)

            await self.influxdb.write_points(points)

    async def publish_mqtt(self, modules, energy_total, count_modules):
        for module in modules.values():
            if module.energy is not None:
                count_modules += 1
                energy_total += module.energy

            await self.event_bus.emit(
                MQTTPublishEvent(
                    f"monitoring/module/{module.info.serialnumber}",
                    module,
                    self.settings.retain
                )
            )

        logger.info(
            "Read from monitoring total energy: {energy_total} kWh "
            "from {count_modules} modules",
            energy_total=energy_total / 1000,
            count_modules=count_modules,
        )

        await self.event_bus.emit(
            MQTTPublishEvent(
                "monitoring/pv_energy_today",
                energy_total,
                self.settings.retain,
            )
        )
