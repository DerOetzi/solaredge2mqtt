import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Any

from loguru import logger

from solaredge2mqtt.core.logging.models import LoggingLevelEnum

if TYPE_CHECKING:
    from loguru import HandlerConfig, Message, Record


class MQTTLoggingSink:
    """Manage MQTT log forwarding state, filtering, and asynchronous publishing."""

    def __init__(self) -> None:
        self._enabled = False
        self._min_level: int = logging.ERROR

    def set_enabled(self, enabled: bool, level: int = logging.ERROR) -> None:
        self._enabled = enabled
        self._min_level = level

    def log_filter(self, record: "Record") -> bool:
        """Allow MQTT log forwarding and suppress recursive MQTT warning/error logs."""
        if not self._enabled:
            return False

        if record["level"].no < self._min_level:
            return False

        if (
            record["name"].startswith("solaredge2mqtt.core.mqtt")
            and record["level"].name in {"WARNING", "ERROR", "CRITICAL"}
        ):
            return False

        return True

    def sink(self, message: "Message") -> None:
        """Format a loguru message and publish it to the MQTT logging topic."""
        from solaredge2mqtt.core.events import EventBus
        from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        payload = (
            f"{message.record['time'].isoformat()} | "
            f"{message.record['level'].name} | "
            f"{message.record['message']}"
        )
        loop.create_task(EventBus.emit(MQTTPublishEvent("logging", payload, False)))


_mqtt_logging_sink = MQTTLoggingSink()


def _disable_pymodbus_stdout_logging() -> None:
    pymodbus_logger = logging.getLogger("pymodbus")
    pymodbus_logger.setLevel(logging.CRITICAL + 1)
    pymodbus_logger.propagate = False
    pymodbus_logger.handlers.clear()


def set_mqtt_logging(enabled: bool, level: int = logging.ERROR) -> None:
    _mqtt_logging_sink.set_enabled(enabled, level)


def _mqtt_log_filter(record: "Record") -> bool:
    return _mqtt_logging_sink.log_filter(record)


def _mqtt_log_sink(message: "Message") -> None:
    return _mqtt_logging_sink.sink(message)


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    _disable_pymodbus_stdout_logging()
    handlers: list[HandlerConfig] = [
        {"sink": sys.stdout, "level": logging_level.level},
        {
            "sink": _mqtt_log_sink,
            "level": logging_level.level,
            "filter": _mqtt_log_filter,
        },
    ]
    logger.configure(handlers=handlers)
