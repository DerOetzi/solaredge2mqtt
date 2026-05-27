from __future__ import annotations

import json
from typing import TYPE_CHECKING

from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent

if TYPE_CHECKING:
    from solaredge2mqtt.core.events import EventBus

_MQTT_MODULE_PREFIXES = ("aiomqtt", "solaredge2mqtt.core.mqtt")


def _is_mqtt_related(record: dict) -> bool:
    """Return True when the log record originates from an MQTT module."""
    name: str = record.get("name", "") or ""
    return any(name.startswith(prefix) for prefix in _MQTT_MODULE_PREFIXES)


def create_mqtt_log_sink(event_bus: EventBus):
    """Return an async loguru sink that publishes log records to MQTT.

    MQTT-related records are excluded to avoid feedback loops.
    """

    async def _sink(message) -> None:  # type: ignore[type-arg]
        record = message.record

        if _is_mqtt_related(record):
            return

        payload = json.dumps(
            {
                "level": record["level"].name,
                "message": record["message"],
                "module": record.get("name", ""),
                "time": record["time"].isoformat(),
            }
        )

        await event_bus.emit(MQTTPublishEvent("logging", payload, retain=False))

    return _sink
