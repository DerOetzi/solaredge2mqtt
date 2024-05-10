from datetime import datetime

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.timer.events import (
    Interval10MinTriggerEvent,
    IntervalBaseTriggerEvent,
)


class Timer:
    def __init__(self, event_bus: EventBus, base_interval: int) -> None:
        self.event_bus = event_bus
        self.base_interval = base_interval

    async def loop(self) -> None:
        timestamp = int(datetime.now().timestamp())

        if timestamp % self.base_interval == 0:
            await self.event_bus.emit(IntervalBaseTriggerEvent())

        if timestamp % 600 == 0:
            await self.event_bus.emit(Interval10MinTriggerEvent())
