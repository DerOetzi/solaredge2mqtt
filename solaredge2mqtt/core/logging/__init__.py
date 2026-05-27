import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

from solaredge2mqtt.core.logging.models import LoggingLevelEnum

if TYPE_CHECKING:
    from solaredge2mqtt.core.events import EventBus


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    logger.configure(handlers=[{"sink": sys.stdout, "level": logging_level.level}])
    _suppress_pymodbus_logging()


def _suppress_pymodbus_logging() -> None:
    """Suppress pymodbus's own logging output to stdout."""
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)
    logging.getLogger("pymodbus").propagate = False


def register_mqtt_log_sink(
    event_bus: "EventBus", logging_level: LoggingLevelEnum
) -> int:
    """Register a loguru sink that publishes log records to MQTT.

    Returns the loguru handler id which can be passed to
    :func:`deregister_mqtt_log_sink` when the MQTT connection ends.
    """
    from solaredge2mqtt.core.logging.mqtt_sink import create_mqtt_log_sink  # noqa: PLC0415

    sink = create_mqtt_log_sink(event_bus)
    handler_id: int = logger.add(sink, level=logging_level.level)
    return handler_id


def deregister_mqtt_log_sink(handler_id: int | None) -> None:
    """Remove a previously registered MQTT log sink."""
    if handler_id is None:
        return
    try:
        logger.remove(handler_id)
    except ValueError:
        pass
