from solaredge2mqtt.core.events.events import BaseEvent


class IntervalBaseTriggerEvent(BaseEvent):
    pass


class Interval1MinTriggerEvent(IntervalBaseTriggerEvent):
    pass


class Interval5MinTriggerEvent(IntervalBaseTriggerEvent):
    pass


class Interval10MinTriggerEvent(IntervalBaseTriggerEvent):
    pass


class Interval15MinTriggerEvent(IntervalBaseTriggerEvent):
    pass
