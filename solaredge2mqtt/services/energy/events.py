from solaredge2mqtt.services.events import ComponentEvent


class EnergyReadEvent(ComponentEvent):
    def __str__(self) -> str:
        return f"{self.component.SOURCE}: {self.component.period}"
