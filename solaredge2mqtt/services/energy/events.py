from solaredge2mqtt.services.energy.models import HistoricEnergy
from solaredge2mqtt.services.events import ComponentEvent


class EnergyReadEvent(ComponentEvent[HistoricEnergy]):
    def __str__(self) -> str:
        return f"energy: {self.component.info.period}"
