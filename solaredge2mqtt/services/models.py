from typing import ClassVar

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel


class ComponentValueGroup(Solaredge2MQTTBaseModel):
    @staticmethod
    def scale_value(
        data: dict[str, str | int],
        value_key: str,
        scale_key: str | None = None,
        digits: int = 2,
    ) -> float:
        if scale_key is None:
            scale_key = f"{value_key}_scale"

        value = int(data[value_key])
        scale = int(data[scale_key])

        return round(value * 10**scale, digits)


class Component(ComponentValueGroup):
    COMPONENT: ClassVar[str] = "unknown"
    SOURCE: ClassVar[str | None] = None

    @property
    def influxdb_tags(self) -> dict[str, str]:
        return {
            "component": self.COMPONENT,
            "source": self.SOURCE,
        }

    def mqtt_topic(self) -> str:
        if self.SOURCE:
            topic = f"{self.SOURCE}/{self.COMPONENT}"
        else:
            topic = self.COMPONENT

        return topic

    def __str__(self) -> str:
        if self.SOURCE:
            name = f"{self.SOURCE}: {self.COMPONENT}"
        else:
            name = self.COMPONENT

        return name
