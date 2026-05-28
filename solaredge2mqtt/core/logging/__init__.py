import asyncio
import logging
import sys
from typing import Any

from loguru import logger

from solaredge2mqtt.core.logging.models import LoggingLevelEnum

_mqtt_logging_enabled = False


def _disable_pymodbus_stdout_logging() -> None:
    pymodbus_logger = logging.getLogger("pymodbus")
    pymodbus_logger.setLevel(logging.CRITICAL + 1)
    pymodbus_logger.propagate = False
    pymodbus_logger.handlers.clear()


def set_mqtt_logging(enabled: bool) -> None:
    global _mqtt_logging_enabled
    _mqtt_logging_enabled = enabled


def _mqtt_log_filter(record: dict[str, Any]) -> bool:
    if not _mqtt_logging_enabled:
        return False

    if (
        record["name"].startswith("solaredge2mqtt.core.mqtt")
        and record["level"].name in {"WARNING", "ERROR", "CRITICAL"}
    ):
        return False

    return True


def _mqtt_log_sink(message: Any) -> asyncio.Task[None] | None:
    from solaredge2mqtt.core.events import EventBus
    from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None

    payload = (
        f"{message.record['time'].isoformat()} | "
        f"{message.record['level'].name} | "
        f"{message.record['message']}"
    )
    return loop.create_task(EventBus.emit(MQTTPublishEvent("logging", payload, False)))


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    _disable_pymodbus_stdout_logging()
    logger.configure(
        handlers=[
            {"sink": sys.stdout, "level": logging_level.level},
            {
                "sink": _mqtt_log_sink,
                "level": logging_level.level,
                "filter": _mqtt_log_filter,
            },
        ]
    )
