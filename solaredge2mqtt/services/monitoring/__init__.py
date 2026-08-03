import asyncio
from datetime import date, datetime, time, timezone

from aiohttp import ClientResponseError

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException
from solaredge2mqtt.core.influxdb import InfluxDBAsync, Point
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.timer.events import (
    Interval5MinTriggerEvent,
    Interval15MinTriggerEvent,
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
LOGICAL_URL = "https://monitoring.solaredge.com/services/layout/logical/generic/v2/site/{site_id}?include-optimizers=true"
ENERGY_BY_INVERTER_URL = (
    "https://monitoring.solaredge.com/services/layout/energy/site/{site_id}/by-inverter"
)
OPTIMIZERS_COMPACT_URL = "https://monitoring.solaredge.com/services/layout/playback/site/{site_id}/optimizers-compact"
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

        self.found_evchargers: bool = False
        self._cached_structure: dict | None = None

        EventBus.register(self)

    async def async_init(self) -> None:
        await self._discover_evchargers()
        await self._load_structure()

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

    @EventBus.subscribe(Interval5MinTriggerEvent)
    async def refresh_evchargers(self, event: Interval5MinTriggerEvent) -> None:
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

            await EventBus.emit(MonitoringOnlineEvent(self.settings.debounce_cycles))
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ConfigurationException,
            InvalidDataException,
        ) as error:
            logger.warning("Unable to refresh EV charger status: {error}", error=error)
            await EventBus.emit(MonitoringOfflineEvent())

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

    async def close(self) -> None:
        await EventBus.emit(MonitoringOfflineEvent())
        await super().close()

    @EventBus.subscribe(Interval15MinTriggerEvent)
    async def get_data(self, event: Interval15MinTriggerEvent | None) -> None:
        try:
            modules = await self.get_modules()

            energy_total = 0
            count_modules = 0

            await self.save_to_influxdb(modules)
            await self.publish_mqtt(modules, energy_total, count_modules)
            await EventBus.emit(MonitoringOnlineEvent(self.settings.debounce_cycles))
        except (ConfigurationException, InvalidDataException):
            await EventBus.emit(MonitoringOfflineEvent())
            raise

    async def get_modules(self) -> dict[str, LogicalModule]:
        energies = await self.get_modules_energy()
        powers = await self.get_modules_power()

        return self.merge_modules(energies, powers)

    async def _load_structure(self) -> None:
        try:
            logical = await self._get_logical()
            site_structure = logical.get("siteStructure")
            if not isinstance(site_structure, dict):
                raise InvalidDataException(
                    "Unexpected response format when reading logical layout"
                )
            self._cached_structure = site_structure
            logger.info("Loaded monitoring site structure")
        except (
            ClientResponseError,
            asyncio.TimeoutError,
            ConfigurationException,
            InvalidDataException,
        ) as error:
            logger.warning(
                "Unable to load monitoring site structure: {error}", error=error
            )

    async def get_modules_energy(self) -> dict[str, LogicalModule]:
        if self._cached_structure is None:
            await self._load_structure()

        if self._cached_structure is None:
            raise InvalidDataException("Monitoring site structure is not available")

        site_structure = self._cached_structure

        inverter_serials = [
            inverter_node["serial"]
            for inverter_node in self._folder_children(site_structure, "INVERTER")
            if inverter_node.get("type") == "INVERTER" and inverter_node.get("serial")
        ]

        energy_by_inverter = await self._get_energy_by_inverter(inverter_serials)

        inverters = self._parse_inverters(site_structure, energy_by_inverter)

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

    async def _get_energy_by_inverter(self, inverter_serials: list[str]) -> dict:
        if not inverter_serials:
            return {}

        today = datetime.now().astimezone().date().isoformat()

        try:
            headers = await self._add_login_headers()

            async with asyncio.timeout(10):
                result = await self._get(
                    ENERGY_BY_INVERTER_URL.format(site_id=self.settings.site_id_secret),
                    params={
                        "start-date": today,
                        "end-date": today,
                        "inverter-serials": ",".join(inverter_serials),
                        "include-max-temperature": "false",
                        "include-color": "true",
                    },
                    headers=headers,
                )

            if not isinstance(result, dict):
                raise InvalidDataException(
                    "Unexpected response format when reading energy by inverter"
                )

            return self._index_energy_by_inverter(result)

        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise InvalidDataException("Unable to read energy by inverter") from error

    @staticmethod
    def _index_energy_by_inverter(data: dict) -> dict:
        index = {}

        for inverter_data in data.get("inverters", []):
            serial = inverter_data.get("serial")
            if not serial:
                continue

            strings_energy = {
                string_data["stringRelativeOrder"]: string_data["energy"]["value"]
                for string_data in inverter_data.get("strings", [])
                if string_data.get("energy") and "stringRelativeOrder" in string_data
            }
            optimizers_energy = {
                optimizer_data["serial"]: optimizer_data["energy"]["value"]
                for optimizer_data in inverter_data.get("optimizers", [])
                if optimizer_data.get("energy") and optimizer_data.get("serial")
            }

            inverter_energy = inverter_data.get("energy")

            index[serial] = {
                "energy": inverter_energy["value"] if inverter_energy else None,
                "strings": strings_energy,
                "optimizers": optimizers_energy,
            }

        return index

    @staticmethod
    def _folder_children(node: dict, folder_name: str) -> list[dict]:
        for child in node.get("children", []):
            if child.get("type") == "FOLDER" and child.get("name") == folder_name:
                return child.get("children", [])

        return []

    def _parse_inverters(
        self, site_structure: dict, energy_by_inverter: dict
    ) -> list[LogicalInverter]:
        inverters = []

        for inverter_node in self._folder_children(site_structure, "INVERTER"):
            if inverter_node.get("type") != "INVERTER":
                logger.info(
                    "Unknown inverter type: {type}", type=inverter_node.get("type")
                )
                continue

            info = LogicalInfo.map(inverter_node)
            inverter_energy = energy_by_inverter.get(inverter_node.get("serial"), {})

            inverter = LogicalInverter.model_validate(
                {"info": info, "energy": inverter_energy.get("energy")}
            )

            self._parse_strings(
                inverter,
                inverter_node,
                inverter_energy.get("strings", {}),
                inverter_energy.get("optimizers", {}),
            )

            inverters.append(inverter)

        return inverters

    def _parse_strings(
        self,
        inverter,
        inverter_node: dict,
        strings_energy: dict,
        optimizers_energy: dict,
    ):
        for string_node in self._folder_children(inverter_node, "STRING"):
            if string_node.get("type") != "STRING":
                continue

            info = LogicalInfo.map(string_node)
            energy = strings_energy.get(string_node.get("order"))

            string = LogicalString.model_validate({"info": info, "energy": energy})

            self._parse_panels(string, string_node, optimizers_energy)

            inverter.strings.append(string)

    def _parse_panels(self, string, string_node: dict, optimizers_energy: dict):
        for optimizer_node in self._folder_children(string_node, "OPTIMIZER"):
            if optimizer_node.get("type") != "OPTIMIZER":
                continue

            info = LogicalInfo.map(optimizer_node)
            energy = optimizers_energy.get(optimizer_node.get("serial"))

            panel = LogicalModule.model_validate({"info": info, "energy": energy})

            string.modules.append(panel)

    async def get_modules_power(self) -> dict[str, dict[datetime, float]]:
        today = datetime.now().astimezone().date()

        try:
            headers = await self._add_login_headers()

            async with asyncio.timeout(10):
                result = await self._get(
                    OPTIMIZERS_COMPACT_URL.format(site_id=self.settings.site_id_secret),
                    params={
                        "resolution": "hours",
                        "start-date": f"{today.isoformat()}T00:00:00Z",
                        "end-date": f"{today.isoformat()}T23:59:59Z",
                    },
                    headers=headers,
                )

            if not isinstance(result, dict):
                raise InvalidDataException(
                    "Unexpected response format when reading optimizer power data"
                )

            modules = self._decode_optimizers_compact(result, today)

            logger.debug(modules)

            return modules
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise InvalidDataException("Unable to read optimizer power data") from error

    @staticmethod
    def _decode_optimizers_compact(
        data: dict, day: date
    ) -> dict[str, dict[datetime, float]]:
        if not isinstance(serials, list) or not serials:
            return {}

        if not isinstance(slots, int) or slots <= 0 or slots > 24:
            return {}

        if not isinstance(power_values, list) or len(power_values) < 2:
            return {}

        payload_start = int(power_values[1])
        if payload_start < 0 or payload_start + len(serials) * slots > len(power_values):
            return {}

        modules: dict[str, dict[datetime, float]] = {}

        for index, serial in enumerate(serials):
            start = payload_start + index * slots
            values = power_values[start : start + slots]

            modules[str(serial)] = {
                datetime.combine(day, time(hour=hour, tzinfo=timezone.utc)).astimezone(): float(
                    value
                )
                for hour, value in enumerate(values)
            }

        return modules

    async def _execute_charge_control(self, device_id: int, level: int) -> None:
        if not self.settings.is_configured:
            logger.warning(
                "Cannot control EV charger charging: monitoring account not configured"
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

    async def _add_login_headers(
        self, headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        token, remember_me_cookie = await self.login()

        merged_headers = dict(headers) if headers else {}
        merged_headers["X-CSRF-TOKEN"] = token
        merged_headers["Cookie"] = (
            f"SPRING_SECURITY_REMEMBER_ME_COOKIE={remember_me_cookie}"
        )
        return merged_headers

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
                    "Login to monitoring account failed.",
                )

            logger.info("Login to monitoring site successful")
            return token, remember_me_cookie
        except (ClientResponseError, asyncio.TimeoutError) as error:
            raise ConfigurationException(
                "Monitoring", "Unable to login to monitoring account"
            ) from error
