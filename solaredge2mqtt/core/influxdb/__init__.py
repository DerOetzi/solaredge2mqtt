from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pkg_resources
from influxdb_client import BucketRetentionRules, InfluxDBClient, Point
from influxdb_client.client.exceptions import InfluxDBError
from influxdb_client.client.influxdb_client_async import (
    InfluxDBClientAsync,
    QueryApiAsync,
)
from pandas import DataFrame
from tzlocal import get_localzone_name

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent
from solaredge2mqtt.core.influxdb.settings import InfluxDBSettings
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent

if TYPE_CHECKING:
    from solaredge2mqtt.services.energy.models import HistoricPeriod
    from solaredge2mqtt.services.energy.settings import PriceSettings


LOCAL_TZ = get_localzone_name()


class InfluxDB:
    def __init__(
        self,
        settings: InfluxDBSettings,
        prices: PriceSettings,
        event_bus: EventBus | None = None,
    ) -> None:
        self.settings: InfluxDBSettings = settings
        self.prices: PriceSettings = prices

        self.event_bus = event_bus
        if self.event_bus:
            self._subscribe_events()

        self.client: InfluxDBClient = InfluxDBClient(
            url=settings.url,
            token=settings.token.get_secret_value(),
            org=settings.org,
        )

        self.write_api = self.client.write_api(
            success_callback=self.write_success_callback,
            error_callback=self.write_error_callback,
            retry_callback=self.write_error_callback,
        )

        self.query_api = self.client.query_api()
        self.delete_api = self.client.delete_api()

        self.client_async: InfluxDBClientAsync | None = None
        self.query_api_async: QueryApiAsync | None = None

        self.flux_cache: dict[str, str] = {}

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(Interval10MinTriggerEvent, self.loop)

    def initialize_buckets(self) -> None:
        buckets_api = self.client.buckets_api()
        bucket = buckets_api.find_bucket_by_name(self.bucket_name)
        retention_rules = BucketRetentionRules(
            type="expire", every_seconds=self.settings.retention
        )

        if bucket is None:
            logger.info(f"Creating bucket '{self.bucket_name}'")
            buckets_api.create_bucket(
                bucket_name=self.bucket_name, retention_rules=retention_rules
            )
        else:
            logger.info(f"Bucket '{self.bucket_name}' already exists.")
            if bucket.retention_rules[0].every_seconds != self.settings.retention:
                logger.info(
                    f"Updating retention rules for bucket '{self.bucket_name}' "
                    + f"to {self.settings.retention} seconds."
                )
                bucket.retention_rules[0] = retention_rules
                buckets_api.update_bucket(bucket=bucket)

    async def loop(self, _) -> None:
        now = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

        logger.info("Aggregate powerflow and energy raw data")
        aggregate_query = self._get_flux_query(
            "aggregate",
            {"PRICE_IN": self.prices.price_in, "PRICE_OUT": self.prices.price_out},
        )
        self.query_api.query(aggregate_query)

        logger.info("Apply retention on raw data")
        retention_time = now - timedelta(hours=self.settings.retention_raw)
        self.delete_from_measurements(
            datetime(1970, 1, 1, tzinfo=timezone.utc),
            retention_time,
            ["powerflow_raw", "battery_raw"],
        )

        if self.event_bus:
            await self.event_bus.emit(InfluxDBAggregatedEvent())

    def delete_from_measurements(
        self, start: datetime, stop: datetime, measurements: list[str]
    ) -> None:
        for measurement in measurements:
            self.delete_from_measurement(start, stop, measurement)

    def delete_from_measurement(
        self, start: datetime, stop: datetime, measurement: str
    ) -> None:
        self.delete_api.delete(
            start, stop, f'_measurement="{measurement}"', self.bucket_name
        )

    @property
    def bucket_name(self) -> str:
        return f"{self.settings.bucket}"

    def write_point(self, point: Point) -> None:
        self.write_points([point])

    def write_points(self, points: list[Point]) -> None:
        self.write_api.write(bucket=self.bucket_name, record=points)

    async def write_points_async(self, points: list[Point]) -> None:
        await self.init_client_async()
        async with self.client_async:
            await self.client_async.write_api().write(
                bucket=self.bucket_name, record=points
            )

    def write_success_callback(self, conf: tuple[str, str, str], data: str) -> None:
        logger.debug(f"InfluxDB batch written: {conf} {data}")

    def write_error_callback(
        self, conf: tuple[str, str, str], data: str, error: InfluxDBError
    ) -> None:
        logger.error(f"InfluxDB error while writting: {conf} {error}")
        logger.debug(data)

    def query_timeunit(
        self, period: HistoricPeriod, measurement: str
    ) -> dict[str, any] | None:
        return self.query_first(
            period.query.query, {"UNIT": period.unit, "MEASUREMENT": measurement}
        )

    def query_first(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> dict[str, any] | None:
        result = self.query(query_name, additional_replacements)
        return result[0] if len(result) > 0 else None

    def query(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> list[dict[str, any]]:

        tables = self.query_api.query(
            self._get_flux_query(query_name, additional_replacements)
        )
        return [record.values for table in tables for record in table.records]

    async def query_dataframe(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> DataFrame:
        await self.init_client_async()
        async with self.client_async:
            return await self.query_api_async.query_data_frame(
                self._get_flux_query(query_name, additional_replacements)
            )

    async def init_client_async(self) -> None:
        self.client_async = InfluxDBClientAsync(
            url=self.settings.url,
            token=self.settings.token.get_secret_value(),
            org=self.settings.org,
        )
        self.query_api_async = self.client_async.query_api()

    def _get_flux_query(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> str:
        if query_name not in self.flux_cache:
            flux = pkg_resources.resource_string(
                __name__, f"./flux/{query_name}.flux"
            ).decode("utf-8")
            flux = (
                flux.replace("{{BUCKET_AGGREGATED}}", self.bucket_name)
                .replace("{{BUCKET_NAME}}", self.bucket_name)
                .replace("{{TIMEZONE}}", LOCAL_TZ)
            )
            self.flux_cache[query_name] = flux

        query = self.flux_cache[query_name]

        if additional_replacements is not None:
            for key, value in additional_replacements.items():
                query = query.replace("{{" + key + "}}", str(value))

        logger.trace(query)

        return query
