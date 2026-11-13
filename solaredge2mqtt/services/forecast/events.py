from __future__ import annotations

from typing import TYPE_CHECKING

from solaredge2mqtt.services.events import ComponentEvent

if TYPE_CHECKING:
    from solaredge2mqtt.services.forecast.models import Forecast


class ForecastEvent(ComponentEvent["Forecast"]):
    @property
    def component(self) -> Forecast:
        return self._component
