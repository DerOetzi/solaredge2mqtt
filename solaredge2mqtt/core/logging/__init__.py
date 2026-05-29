import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

from solaredge2mqtt.core.logging.models import LoggingLevelEnum

if TYPE_CHECKING:
    from loguru import HandlerConfig


def _disable_pymodbus_stdout_logging() -> None:
    pymodbus_logger = logging.getLogger("pymodbus")
    pymodbus_logger.setLevel(logging.CRITICAL + 1)
    pymodbus_logger.propagate = False
    pymodbus_logger.handlers.clear()


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    _disable_pymodbus_stdout_logging()
    handlers: list[HandlerConfig] = [
        {"sink": sys.stdout, "level": logging_level.level}
    ]
    logger.configure(handlers=handlers)
