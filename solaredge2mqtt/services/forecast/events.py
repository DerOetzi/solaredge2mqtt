from solaredge2mqtt.services.events import ComponentEvent
from solaredge2mqtt.services.forecast.models import Forecast


class ForecastEvent(ComponentEvent[Forecast]): ...  # pragma: no cover
