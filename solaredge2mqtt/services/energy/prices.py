from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from solaredge2mqtt.services.energy.settings import PriceSettings


class PriceResolver:
    def __init__(self, settings: PriceSettings) -> None:
        self.settings: PriceSettings = settings

    @property
    def is_configured(self) -> bool:
        return self.settings.is_configured

    def consumption_at(self, timestamp: int) -> float:
        return self.settings.price_in

    def delivery_at(self, timestamp: int) -> float:
        return self.settings.price_out
