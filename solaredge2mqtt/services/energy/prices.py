from __future__ import annotations

from datetime import datetime, timedelta, tzinfo
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

from tzlocal import get_localzone_name

from solaredge2mqtt.services.energy.settings import WEEKDAYS

if TYPE_CHECKING:
    from solaredge2mqtt.services.energy.settings import (
        PriceScheduleEntry,
        PriceSettings,
    )


class PriceResolver:
    def __init__(self, settings: PriceSettings, tz: tzinfo | None = None) -> None:
        self.settings: PriceSettings = settings
        self.tz: tzinfo = tz or ZoneInfo(get_localzone_name())

    @property
    def is_configured(self) -> bool:
        return self.settings.is_configured

    def consumption_at(self, timestamp: int) -> float:
        return self._price_at(timestamp, "consumption", self.settings.price_in)

    def delivery_at(self, timestamp: int) -> float:
        return self._price_at(timestamp, "delivery", self.settings.price_out)

    def _price_at(
        self,
        timestamp: int,
        direction: Literal["consumption", "delivery"],
        fallback: float,
    ) -> float:
        local = datetime.fromtimestamp(timestamp, tz=self.tz)

        for entry in self.settings.schedule:
            price = getattr(entry, direction)
            if price is not None and _matches(entry, local):
                return price

        return fallback


def _matches(entry: PriceScheduleEntry, local: datetime) -> bool:
    minute = local.hour * 60 + local.minute

    if entry.wraps_midnight and minute < entry.end_minute:
        day = local - timedelta(days=1)
    elif entry.start_minute <= minute and (
        entry.wraps_midnight or minute < entry.end_minute
    ):
        day = local
    else:
        return False

    if entry.months and day.month not in entry.months:
        return False

    return not entry.weekdays or WEEKDAYS[day.weekday()] in entry.weekdays
