from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.models import Component


class ComponentEvent(BaseEvent):
    def __init__(self, component: Component):
        self._component = component

    @property
    def component(self) -> Component:
        return self._component

    def __str__(self) -> str:
        return str(self._component)


class ComponentsEvent(BaseEvent):
    def __init__(self, components: dict[str, Component]):
        self._components = components

    @property
    def components(self) -> dict[str, Component]:
        return self._components

    def __str__(self) -> str:
        return str(self._components)
