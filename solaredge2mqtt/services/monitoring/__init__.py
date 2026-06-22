import asyncio
import json
from datetime import datetime, timezone

from aiohttp import ClientResponseError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync, Point
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import (
    Interval15MinTriggerEvent,
    IntervalBaseTriggerEvent,
)
from solaredge2mqtt.services.http_async import HTTPClientAsync
from solaredge2mqtt.services.monitoring.events import (
    EVChargerChargeLevelEvent,
    EVChargerChargeLevelSubscribeEvent,
    EVChargerReadEvent,
    MonitoringOfflineEvent,
    MonitoringOnlineEvent,
)
from solaredge2mqtt.services.monitoring.models import (
    EVCharger,
    LogicalInfo,
    LogicalInverter,
    LogicalModule,
    LogicalString,
)
from solaredge2mqtt.services.monitoring.settings import MonitoringSettings

LOGIN_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/login"
LOGICAL_URL = "https://monitoring.solaredge.com/solaredge-apigw/api/sites/{site_id}/layout/logical"
POWER_PUBLIC_URL = "https://monitoring.solaredge.com/solaredge-web/p/playbackData"
DEVICES_URL = "https://monitoring.solaredge.com/services/api/homeautomation/v1.0/sites/{site_id}/devices"
CHARGING_CONTROL_URL = "https://monitoring.solaredge.com/services/m/api/homeautomation/v1.0/{site_id}/devices/{device_id}/activationState"
CONTENT_TYPE_FORM_URLENCODED = "application/x-www-form-urlencoded"


class MonitoringSite(HTTPClientAsync):
    def __init__(
        self,
        settings: MonitoringSettings,
        influxdb: InfluxDBAsync | None,
    ) -> None:
        super().__init__("Monitoring Site")
        self.settings = settings

        self.influxdb: InfluxDBAsync | None = influxdb
        self._remember_me_cookie: str | None = None

        self.found_evchargers: bool = False

        EventBus.register(self)

    async def async_init(self) -> None:
        await self._discover_evchargers()

    async def _discover_evchargers(self) -> None:
        try:
            headers = await self._add_login_headers()

            async with asyncio.timeout(10):
                result = await self._get(
                    DEVICES_URL.format(site_id=self.settings.site_id_secret),
                    headers=headers,
                )

            charger_devices = self._extract_evchargers(result)
            if not charger_devices:
                logger.info("No controllable EV charger found in monitoring account")
                return

            self.found_evchargers = True

            for device in charger_devices:
                charger = EVCharger.from_device(device)

                await EventBus.emit(
                    EVChargerChargeLevelSubscribeEvent(charger.mqtt_chargelevel_topic())
                )
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ConfigurationException,
            InvalidDataException,
        ) as error:
            logger.warning("Unable to discover EV chargers: {error}", error=error)

    @EventBus.subscribe(IntervalBaseTriggerEvent)
    async def refresh_evchargers(self, event: IntervalBaseTriggerEvent) -> None:
        if not self.found_evchargers:
            return

        try:
            headers = await self._add_login_headers()

            async with asyncio.timeout(10):
                result = await self._get(
                    DEVICES_URL.format(site_id=self.settings.site_id_secret),
                    headers=headers,
                )

            for device in self._extract_evchargers(result):
                evcharger = EVCharger.from_device(device)
                await EventBus.emit(EVChargerReadEvent(evcharger))
                await EventBus.emit(
                    MQTTPublishEvent(
                        evcharger.mqtt_topic(), evcharger, self.settings.retain
                    )
                )
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ConfigurationException,
            InvalidDataException,
        ) as error:
            logger.warning("Unable to refresh EV charger status: {error}", error=error)

    @staticmethod
    def _extract_evchargers(result: object) -> list[dict[str, object]]:
        if not isinstance(result, dict):
            return []

        devices_by_type = result.get("devicesByType")
        if not isinstance(devices_by_type, dict):
            return []

        chargers = devices_by_type.get("EV_CHARGER", [])
        if not isinstance(chargers, list):
            return []

        return [
            charger
            for charger in chargers
            if isinstance(charger, dict) and charger.get("reporterId") is not None
        ]

    @EventBus.subscribe(EVChargerChargeLevelEvent)
    async def handle_charge_command(self, event: EVChargerChargeLevelEvent) -> None:
        topic_parts = event.topic.split("/")
        try:
            idx = topic_parts.index("evcharger")
            reporter_id = int(topic_parts[idx + 1])
        except (ValueError, IndexError):
            logger.warning(
                "Cannot extract device id from EV charger command topic: {topic}",
                topic=event.topic,
            )
            return

        level = event.input.level
        logger.info(
            "Requesting EV charger charge level {level}% for device {reporter_id}",
            level=level,
            reporter_id=reporter_id,
        )
        await self._execute_charge_control(reporter_id, level)

    @EventBus.subscribe(Interval15MinTriggerEvent)
    async def get_data(self, event: Interval15MinTriggerEvent | None) -> None:
        try:
            energies = await self.get_modules_energy()
            powers = await self.get_modules_power()

            modules = self.merge_modules(energies, powers)

            energy_total = 0
            count_modules = 0

            await self.save_to_influxdb(modules)
            await self.publish_mqtt(modules, energy_total, count_modules)
            await EventBus.emit(MonitoringOnlineEvent(self.settings.debounce_cycles))
        except (ConfigurationException, InvalidDataException):
            await EventBus.emit(MonitoringOfflineEvent())
            raise

    async def get_modules_energy(self) -> dict[str, LogicalModule]:
        logical = await self._get_logical()

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

    async def _get_logical(self) -> dict:
        try:
            headers = await self._add_login_headers(
                {
                    "Content-Type": CONTENT_TYPE_FORM_URLENCODED,
                }
            )

            async with asyncio.timeout(10):
                result = await self._get(
                    LOGICAL_URL.format(site_id=self.settings.site_id_secret),
                    headers=headers,
                )

                if not isinstance(result, dict):
                    raise InvalidDataException(
                        "Unexpected response format when reading logical layout"
                    )

                return result

        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise InvalidDataException("Unable to read logical layout") from error

    def _parse_inverters(self, inverter_objs, reporters_data) -> list[LogicalInverter]:
        inverters = []

        for inverter_obj in inverter_objs:
            info = LogicalInfo.map(inverter_obj["data"])
            if "INVERTER" in info["type"]:
                inverter = LogicalInverter.model_validate(
                    {
                        "info": info,
                        "energy": (
                            reporters_data[info["identifier"]]["unscaledEnergy"]
                            if info["identifier"] in reporters_data
                            else None
                        ),
                    }
                )

                self._parse_strings(inverter, inverter_obj["children"], reporters_data)

                inverters.append(inverter)

            else:
                logger.info("Unknown inverter type: {type}", type=info["type"])

        return inverters

    def _parse_strings(self, inverter, string_objs, reporters_data):
        for string_obj in string_objs:
            info = LogicalInfo.map(string_obj["data"])
            string = LogicalString.model_validate(
                {
                    "info": info,
                    "energy": (
                        reporters_data[info["identifier"]]["unscaledEnergy"]
                        if info["identifier"] in reporters_data
                        else None
                    ),
                },
            )

            self._parse_panels(string, string_obj["children"], reporters_data)

            inverter.strings.append(string)

    def _parse_panels(self, string, panel_objs, reporters_data):
        for panel_obj in panel_objs:
            info = LogicalInfo.map(panel_obj["data"])
            panel = LogicalModule.model_validate(
                {
                    "info": info,
                    "energy": (
                        reporters_data[info["identifier"]]["unscaledEnergy"]
                        if info["identifier"] in reporters_data
                        else None
                    ),
                },
            )

            string.modules.append(panel)

    async def get_modules_power(self) -> dict[str, dict[datetime, float]]:
        playback = await self._get_playback()

        modules = {}

        for date_str, reporters_data in playback["reportersData"].items():
            date = datetime.strptime(date_str, "%a %b %d %H:%M:%S GMT %Y").astimezone()

            for entries in reporters_data.values():
                for entry in entries:
                    key = entry["key"]
                    if key not in modules:
                        modules[key] = {}

                    modules[key][date] = float(entry["value"])

        logger.debug(modules)

        return modules

    async def _get_playback(self) -> dict:
        try:
            headers = await self._add_login_headers(
                {
                    "Content-Type": CONTENT_TYPE_FORM_URLENCODED,
                }
            )

            async with asyncio.timeout(10):
                playback_data = await self._post(
                    POWER_PUBLIC_URL,
                    data={
                        "fieldId": self.settings.site_id_secret,
                        "timeUnit": str(4),
                        "CSRF": headers.get("X-CSRF-TOKEN", ""),
                    },
                    headers=headers,
                    expect_json=False,
                )

            if not isinstance(playback_data, str):
                raise InvalidDataException(
                    "Unexpected response format when reading playback data"
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

            return json.loads(response)
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise InvalidDataException("Unable to read logical layout") from error

    async def _execute_charge_control(self, device_id: int, level: int) -> None:
        if not self.settings.is_configured:
            logger.warning(
                "Cannot control wallbox charging: monitoring account not configured"
            )
            return

        try:
            headers = await self._add_login_headers()

            async with asyncio.timeout(10):
                result = await self._put(
                    CHARGING_CONTROL_URL.format(
                        site_id=self.settings.site_id_secret,
                        device_id=device_id,
                    ),
                    json={
                        "mode": "MANUAL",
                        "level": level,
                        "duration": None,
                    },
                    headers=headers,
                )

            if isinstance(result, dict) and result.get("status") == "PASSED":
                logger.info(
                    "EV charger level set to {level}% (device {device_id})",
                    level=level,
                    device_id=device_id,
                )
            else:
                logger.warning(
                    "EV charger level control was not accepted: {result}", result=result
                )
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ConfigurationException,
            InvalidDataException,
        ) as error:
            logger.warning(
                "Unable to control EV charger charging: {error}", error=error
            )

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

            await EventBus.emit(
                MQTTPublishEvent(
                    f"monitoring/module/{module.info.serialnumber}",
                    module,
                    self.settings.retain,
                )
            )

        logger.info(
            "Read from monitoring total energy: {energy_total} kWh "
            "from {count_modules} modules",
            energy_total=energy_total / 1000,
            count_modules=count_modules,
        )

        await EventBus.emit(
            MQTTPublishEvent(
                "monitoring/pv_energy_today",
                energy_total,
                self.settings.retain,
            )
        )

    async def _add_login_headers(self, headers: dict[str, str] = {}) -> dict[str, str]:
        token, remember_me_cookie = await self.login()

        headers["X-CSRF-TOKEN"] = token
        headers["Cookie"] = f"SPRING_SECURITY_REMEMBER_ME_COOKIE={remember_me_cookie}"
        return headers

    async def login(self) -> tuple[str, str]:
        try:
            token = self.get_cookie("CSRF-TOKEN")
            remember_me_cookie = self.get_cookie("SPRING_SECURITY_REMEMBER_ME_COOKIE")

            if token and remember_me_cookie:
                return token, remember_me_cookie

            async with asyncio.timeout(10):
                await self._post(
                    LOGIN_URL,
                    headers={"Content-Type": CONTENT_TYPE_FORM_URLENCODED},
                    data={
                        "j_username": self.settings.username_value,
                        "j_password": self.settings.password_secret,
                    },
                    expect_json=False,
                )

            token = self.get_cookie("CSRF-TOKEN")
            remember_me_cookie = self.get_cookie("SPRING_SECURITY_REMEMBER_ME_COOKIE")

            if not (token and remember_me_cookie):
                raise ConfigurationException(
                    "Monitoring",
                    "Login to monitoring account failed, CSRF token not found",
                )

            logger.info("Login to monitoring site successful")
            return token, remember_me_cookie
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise ConfigurationException(
                "Monitoring", "Unable to login to monitoring account"
            ) from error
