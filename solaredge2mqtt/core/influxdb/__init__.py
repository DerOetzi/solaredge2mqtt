from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib import resources
from typing import TYPE_CHECKING

from influxdb_client import BucketRetentionRules, InfluxDBClient, Point
from influxdb_client.client.bucket_api import BucketsApi
from influxdb_client.client.delete_api import DeleteApi
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync
from influxdb_client.client.query_api_async import QueryApiAsync
from tzlocal import get_localzone_name

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.influxdb.events import InfluxDBAggregatedEvent
from solaredge2mqtt.core.influxdb.settings import InfluxDBSettings
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent

if TYPE_CHECKING:
    from pandas import DataFrame

    from solaredge2mqtt.services.energy.models import HistoricPeriod
    from solaredge2mqtt.services.energy.settings import PriceSettings

LOCAL_TZ = get_localzone_name()


class InfluxDBAsync:
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

        self.client_async: InfluxDBClientAsync | None = None
        self.client_sync: InfluxDBClient = InfluxDBClient(
            **self.settings.client_params)

        self.flux_cache: dict[str, str] = {}

    def _subscribe_events(self) -> None:
        self.event_bus.subscribe(Interval10MinTriggerEvent, self.loop)

    def init(self) -> None:
        self.client_async = InfluxDBClientAsync(**self.settings.client_params)

        self.initialize_buckets()

    def initialize_buckets(self) -> None:
        bucket = self.buckets_api.find_bucket_by_name(self.bucket_name)
        retention_rules = BucketRetentionRules(
            type="expire", every_seconds=self.settings.retention
        )

        if bucket is None:
            logger.info(f"Creating bucket '{self.bucket_name}'")
            self.buckets_api.create_bucket(
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
                self.buckets_api.update_bucket(bucket=bucket)

    @property
    def buckets_api(self) -> BucketsApi:
        return self.client_sync.buckets_api()

    async def loop(self, _) -> None:
        now = datetime.now(tz=timezone.utc).replace(
            minute=0, second=0, microsecond=0)

        logger.info("Aggregate powerflow and energy raw data")
        aggregate_query = self._get_flux_query(
            "aggregate",
            {"PRICE_IN": self.prices.price_in, "PRICE_OUT": self.prices.price_out},
        )
        await self.query_api.query(aggregate_query)

        logger.info("Apply retention on raw data")
        retention_time = now - timedelta(hours=self.settings.retention_raw)
        self.delete_from_measurements(
            datetime(1970, 1, 1, tzinfo=timezone.utc),
            retention_time,
            ["powerflow_raw", "battery_raw"],
        )

        if self.event_bus:
            await self.event_bus.emit(InfluxDBAggregatedEvent())

    @property
    def query_api(self) -> QueryApiAsync:
        return self.client_async.query_api()

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
    def delete_api(self) -> DeleteApi:
        return self.client_sync.delete_api()

    @property
    def bucket_name(self) -> str:
        return f"{self.settings.bucket}"

    async def write_point(self, point: Point) -> None:
        await self.write_points([point])

    async def write_points(self, points: list[Point]) -> None:
        await self.client_async.write_api().write(
            bucket=self.bucket_name, record=points
        )

    async def query_timeunit(
        self, period: HistoricPeriod, measurement: str
    ) -> list[dict[str, any]] | None:
        results = await self.query(
            period.query.query, {"UNIT": period.unit,
                                 "MEASUREMENT": measurement}
        )

        return results if len(results) > 0 else None

    async def query_first(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> dict[str, any] | None:
        result = await self.query(query_name, additional_replacements)
        return result[0] if len(result) > 0 else None

    async def query(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> list[dict[str, any]]:

        tables = await self.query_api.query(
            self._get_flux_query(query_name, additional_replacements)
        )
        return [record.values for table in tables for record in table.records]

    async def query_dataframe(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> DataFrame:
        return await self.query_api.query_data_frame(
            self._get_flux_query(query_name, additional_replacements)
        )

    def _get_flux_query(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> str:
        if query_name not in self.flux_cache:
            with resources.files(__package__).joinpath(
                f"flux/{query_name}.flux"
            ).open("r", encoding="utf-8") as f:
                flux = f.read()

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

    async def close(self) -> None:
        if self.client_async:
            await self.client_async.close()
            self.client_async = None
