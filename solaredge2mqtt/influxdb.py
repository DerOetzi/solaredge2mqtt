from influxdb_client import InfluxDBClient

from solaredge2mqtt.models import Component, PowerFlow
from solaredge2mqtt.settings import ServiceSettings


class InfluxDB:
    def __init__(self, settings: ServiceSettings) -> None:
        self.bucket = settings.influxdb_bucket
        self.client = InfluxDBClient(
            url=f"{settings.influxdb_host}:{settings.influxdb_port}",
            token=settings.influxdb_token,
            org=settings.influxdb_org,
        )
        self.write_api = self.client.write_api()

    def write_components(
        self, *args: list[Component | dict[str, Component] | None]
    ) -> None:
        points = []
        for component in args:
            if isinstance(component, Component):
                points.append(
                    {
                        "measurement": "component",
                        "tags": component.influxdb_tags,
                        "fields": component.influxdb_fields(),
                    }
                )
            elif isinstance(component, dict):
                for name, component in component.items():
                    points.append(
                        {
                            "measurement": "component",
                            "tags": {"name": name, **component.influxdb_tags},
                            "fields": component.influxdb_fields(),
                        }
                    )

        self.write_api.write(self.bucket, record=points)

    def write_component(self, component: Component) -> None:
        point = {
            "measurement": "component",
            "tags": component.influxdb_tags,
            "fields": component.influxdb_fields(),
        }
        self.write_api.write(self.bucket, record=[point])

    def write_powerflow(self, powerflow: PowerFlow) -> None:
        point = {
            "measurement": "powerflow",
            "tags": {},
            "fields": powerflow.influxdb_fields(),
        }
        self.write_api.write(self.bucket, record=[point])
