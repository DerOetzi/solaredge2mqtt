from datetime import datetime

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.timer.events import (
    Interval1MinTriggerEvent,
    Interval5MinTriggerEvent,
    Interval10MinTriggerEvent,
    Interval15MinTriggerEvent,
    IntervalBaseTriggerEvent,
)


class Timer:
    def __init__(self, base_interval: int) -> None:
        self.base_interval = base_interval
        EventBus.register(self)

    async def loop(self) -> None:
        timestamp = int(datetime.now().timestamp())

        if timestamp % self.base_interval == 0:
            await EventBus.emit(IntervalBaseTriggerEvent())

        timestamp -= self.base_interval - 1

        if timestamp % 60 == 0:
            await EventBus.emit(Interval1MinTriggerEvent())

        timestamp -= self.base_interval

        if timestamp % 300 == 0:
            await EventBus.emit(Interval5MinTriggerEvent())

        timestamp -= self.base_interval

        if timestamp % 600 == 0:
            await EventBus.emit(Interval10MinTriggerEvent())
        timestamp -= self.base_interval

        if timestamp % 900 == 0:
            await EventBus.emit(Interval15MinTriggerEvent())
