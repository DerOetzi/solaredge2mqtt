from influxdb_client import (
    InfluxDBClient,
    Point,
    BucketRetentionRules,
    BucketsApi,
    TaskCreateRequest,
)

import pkg_resources

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models import Component, Powerflow
from solaredge2mqtt.settings import ServiceSettings


class InfluxDB:
    def __init__(self, settings: ServiceSettings) -> None:
        self.prefix: str = settings.influxdb_prefix

        self.retention_raw: int = settings.influxdb_retention_raw
        self.retention_aggregated: int = settings.influxdb_retention_aggregated

        self.org: str = settings.influxdb_org

        self.client: InfluxDBClient = InfluxDBClient(
            url=f"{settings.influxdb_host}:{settings.influxdb_port}",
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )

        self.loop_points: list[Point] = []

        self.flux_cache: dict[str, str] = {}

    def initialize_buckets(self) -> None:
        buckets_api = self.client.buckets_api()
        self._create_or_update_bucket(buckets_api, self.bucket_raw, self.retention_raw)
        self._create_or_update_bucket(
            buckets_api, self.bucket_aggregated, self.retention_aggregated
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
        return f"{self.prefix}_raw"

    @property
    def bucket_aggregated(self) -> str:
        return f"{self.prefix}"

    def initialize_task(self) -> None:
        tasks_api = self.client.tasks_api()
        tasks = tasks_api.find_tasks(name=self.task_name)
        if not tasks:
            flux = self._get_flux_query("aggregation").replace(
                "TASK_NAME", self.task_name
            )

            logger.info(f"Creating task '{self.task_name}'")
            logger.debug(flux)
            task_request = TaskCreateRequest(
                flux=flux, org_id=self.org, status="active"
            )
            tasks_api.create_task(task_create_request=task_request)
        else:
            logger.info(f"Task '{self.task_name}' already exists.")

    def _get_flux_query(self, query_name: str) -> str:
        if query_name not in self.flux_cache:
            flux = pkg_resources.resource_string(
                __name__, f"resources/{query_name}.flux"
            ).decode("utf-8")
            flux = flux.replace("BUCKET_RAW", self.bucket_raw).replace(
                "BUCKET_AGGREGATED", self.bucket_aggregated
            )
            self.flux_cache[query_name] = flux

        return self.flux_cache[query_name]

    @property
    def task_name(self) -> str:
        return f"{self.prefix}_aggregation"

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

        for key, value in component.influxdb_fields().items():
            point.field(key, value)

        return point

    def write_powerflow(self, powerflow: Powerflow) -> None:
        point = Point("powerflow")
        for key, value in powerflow.influxdb_fields().items():
            point.field(key, value)
        self.loop_points.append(point)

    def flush_loop(self) -> None:
        write_api = self.client.write_api()
        write_api.write(bucket=self.bucket_raw, record=self.loop_points)
        self.loop_points = []

    def energy_loop(self) -> None:
        pass
