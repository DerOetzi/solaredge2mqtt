import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

from solaredge2mqtt.core.logging.models import LoggingLevelEnum

if TYPE_CHECKING:
    from loguru import HandlerConfig


class InterceptHandler(logging.Handler):
    """Forward stdlib `logging` records into loguru.

    Without this, any dependency that logs via the standard library
    (pvlearn, for one) is invisible: the root logger has no handler by
    default, so its records are silently dropped rather than reaching the
    stdout sink `initialize_logging` configures for loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _disable_pymodbus_stdout_logging() -> None:
    pymodbus_logger = logging.getLogger("pymodbus")
    pymodbus_logger.setLevel(logging.CRITICAL + 1)
    pymodbus_logger.propagate = False
    pymodbus_logger.handlers.clear()


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    _disable_pymodbus_stdout_logging()
    handlers: list[HandlerConfig] = [{"sink": sys.stdout, "level": logging_level.level}]
    logger.configure(handlers=handlers)

    # level=0 lets every stdlib record reach the InterceptHandler; loguru's
    # own sink level above is what actually filters them, same as for any
    # native loguru call.
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
