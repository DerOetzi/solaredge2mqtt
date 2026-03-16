from abc import abstractmethod
from typing import ClassVar, TypeVar

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel


class Component(Solaredge2MQTTBaseModel):
    # TODO : Remove SOURCE and COMPONENT
    COMPONENT: ClassVar[str] = "unknown"
    SOURCE: ClassVar[str | None] = None

    @property
    def influxdb_tags(self) -> dict[str, str]:
        return {
            "component": self.COMPONENT,
            "source": self.SOURCE or "",
        }

    def mqtt_topic(self) -> str:
        if self.SOURCE:
            topic = f"{self.SOURCE}/{self.COMPONENT}"
        else:
            topic = self.COMPONENT

        return topic

    @abstractmethod
    def homeassistant_device_info(self) -> dict[str, str]:
        pass

    def __str__(self) -> str:
        if self.SOURCE:
            name = f"{self.SOURCE}: {self.COMPONENT}"
        else:
            name = self.COMPONENT

        return name


TComponent = TypeVar("TComponent", bound=Component)
