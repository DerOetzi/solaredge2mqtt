from typing import Any

import pkg_resources
from influxdb_client import (
    BucketRetentionRules,
    BucketsApi,
    InfluxDBClient,
    Point,
    TaskCreateRequest,
)
from influxdb_client.client.exceptions import InfluxDBError
from pandas import DataFrame

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import Component, ForecastPeriod, HistoricPeriod, Powerflow
from solaredge2mqtt.settings import InfluxDBSettings


class InfluxDB:
    def __init__(self, settings: InfluxDBSettings) -> None:
        self.settings = settings

        self.client: InfluxDBClient = InfluxDBClient(
            url=f"{settings.host}:{settings.port}",
            token=settings.token.get_secret_value(),
            org=settings.org,
        )

        self.write_api = self.client.write_api(
            success_callback=self.write_success_callback,
            error_callback=self.write_error_callback,
            retry_callback=self.write_error_callback,
        )

        self.query_api = self.client.query_api()

        self.loop_points: list[Point] = []

        self.flux_cache: dict[str, str] = {}

    def initialize_buckets(self) -> None:
        buckets_api = self.client.buckets_api()
        self._create_or_update_bucket(
            buckets_api, self.bucket_raw, self.settings.retention_raw
        )
        self._create_or_update_bucket(
            buckets_api,
            self.bucket_aggregated,
            self.settings.retention_aggregated,
        )

    def _create_or_update_bucket(
        self, buckets_api: BucketsApi, bucket_name: str, retention: int
    ) -> None:
        bucket = buckets_api.find_bucket_by_name(bucket_name)
        retention_rules = BucketRetentionRules(type="expire", every_seconds=retention)

        if bucket is None:
            logger.info(f"Creating bucket '{bucket_name}'")
            buckets_api.create_bucket(
                bucket_name=bucket_name, retention_rules=retention_rules
            )
        else:
            logger.info(f"Bucket '{bucket_name}' already exists.")
            if bucket.retention_rules[0].every_seconds != retention:
                logger.info(
                    f"Updating retention rules for bucket '{bucket_name}' to {retention} seconds."
                )
                bucket.retention_rules[0] = retention_rules
                buckets_api.update_bucket(bucket=bucket)

    @property
    def bucket_raw(self) -> str:
        return f"{self.settings.prefix}_raw"

    @property
    def bucket_aggregated(self) -> str:
        return f"{self.settings.prefix}"

    def initialize_task(self) -> None:
        tasks_api = self.client.tasks_api()
        tasks = tasks_api.find_tasks(name=self.task_name)
        flux = self._get_flux_query(
            "aggregation",
            {"TASK_NAME": self.task_name, "UNIT": self.settings.aggregate_interval},
        )

        if not tasks:
            task_request = TaskCreateRequest(
                flux=flux, org_id=self.settings.org, status="active"
            )
            logger.info(f"Creating task '{self.task_name}'")
            logger.debug(flux)
            tasks_api.create_task(task_create_request=task_request)
        else:
            logger.info(f"Task '{self.task_name}' already exists.")

            new_flux = self._strip_flux(flux)
            stored_flux = self._strip_flux(tasks[0].flux)

            if (
                new_flux != stored_flux
                or tasks[0].every != self.settings.aggregate_interval
            ):
                logger.info(f"Updating task '{self.task_name}'")
                logger.debug(flux)
                tasks[0].flux = flux
                tasks[0].every = self.settings.aggregate_interval
                tasks_api.update_task(tasks[0])

    @staticmethod
    def _strip_flux(flux: str) -> str:
        return "".join(line.strip() for line in flux.splitlines()).replace(" ", "")

    @property
    def task_name(self) -> str:
        return f"{self.settings.prefix}_aggregation"

    def write_components(
        self, *args: list[Component | dict[str, Component] | None]
    ) -> None:
        for component in args:
            if isinstance(component, Component):
                self.loop_points.append(self._create_component_point(component))
            elif isinstance(component, dict):
                for name, component in component.items():
                    self.loop_points.append(
                        self._create_component_point(component, {"name": name})
                    )

    def write_component(self, component: Component) -> None:
        self.loop_points.append(self._create_component_point(component))

    def _create_component_point(
        self, component: Component, additional_tags: dict[str, str] = None
    ) -> Point:
        point = Point("component")

        for key, value in component.influxdb_tags.items():
            point.tag(key, value)

        if additional_tags is not None:
            for key, value in additional_tags.items():
                point.tag(key, value)

        for key, value in component.model_dump_influxdb().items():
            point.field(key, value)

        return point

    def write_powerflow(self, powerflow: Powerflow) -> None:
        point = Point("powerflow")
        for key, value in powerflow.model_dump_influxdb().items():
            point.field(key, value)
        self.loop_points.append(point)

    def flush_loop(self) -> None:
        self.write_api.write(bucket=self.bucket_raw, record=self.loop_points)
        self.loop_points = []

    def write_point_to_raw_bucket(self, point: Point) -> None:
        self.write_points_to_raw_bucket([point])

    def write_points_to_raw_bucket(self, points: list[Point]) -> None:
        self.write_api.write(bucket=self.bucket_raw, record=points)

    def write_point_to_aggregated_bucket(self, point: Point) -> None:
        self.write_points_to_aggregated_bucket([point])

    def write_points_to_aggregated_bucket(self, points: list[Point]) -> None:
        self.write_api.write(bucket=self.bucket_aggregated, record=points)

    def write_success_callback(self, conf: tuple[str, str, str], data: str) -> None:
        logger.debug(f"InfluxDB batch written: {conf} {data}")

    def write_error_callback(
        self, conf: tuple[str, str, str], data: str, error: InfluxDBError
    ) -> None:
        logger.error(f"InfluxDB error while writting: {conf} {error}")
        logger.debug(data)

    def query_timeunit(
        self, period: HistoricPeriod | ForecastPeriod, measurement: str
    ) -> dict[str, Any] | None:
        return self.query_first(
            period.query.query, {"UNIT": period.unit, "MEASUREMENT": measurement}
        )

    def query_first(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> dict[str, Any] | None:
        result = self.query(query_name, additional_replacements)
        return result[0] if len(result) > 0 else None

    def query(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> list[dict[str, Any]]:

        tables = self.query_api.query(
            self._get_flux_query(query_name, additional_replacements)
        )
        return [record.values for table in tables for record in table.records]

    def query_dataframe(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> DataFrame:
        return self.query_api.query_data_frame(
            self._get_flux_query(query_name, additional_replacements)
        )

    def _get_flux_query(
        self, query_name: str, additional_replacements: dict[str, any] | None = None
    ) -> str:
        if query_name not in self.flux_cache:
            flux = pkg_resources.resource_string(
                __name__, f"resources/{query_name}.flux"
            ).decode("utf-8")
            flux = (
                flux.replace("{{BUCKET_RAW}}", self.bucket_raw)
                .replace("{{BUCKET_AGGREGATED}}", self.bucket_aggregated)
                .replace("{{TIMEZONE}}", self.settings.timezone)
            )
            self.flux_cache[query_name] = flux

        query = self.flux_cache[query_name]

        if additional_replacements is not None:
            for key, value in additional_replacements.items():
                query = query.replace("{{" + key + "}}", str(value))

        logger.trace(query)

        return query
