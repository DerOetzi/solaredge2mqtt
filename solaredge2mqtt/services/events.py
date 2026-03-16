from typing import Generic

from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.models import TComponent


class ComponentEvent(BaseEvent, Generic[TComponent]):
    def __init__(self, component: TComponent):
        self._component = component

    @property
    def component(self) -> TComponent:
        return self._component

    def __str__(self) -> str:
        return str(self._component)


class ComponentsEvent(BaseEvent, Generic[TComponent]):
    def __init__(self, components: dict[str, TComponent]):
        self._components = components

    @property
    def components(self) -> dict[str, TComponent]:
        return self._components

    def __str__(self) -> str:
        return str(self._components)
