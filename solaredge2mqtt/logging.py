import logging
import sys

from loguru import logger

from solaredge2mqtt.models import EnumModel

LOGGING_DEVICE_INFO = "{device} ({info.manufacturer} {info.model} {info.serialnumber})"


class LoggingLevelEnum(EnumModel):
    DEBUG = "DEBUG", logging.DEBUG
    INFO = "INFO", logging.INFO
    WARNING = "WARNING", logging.WARNING
    ERROR = "ERROR", logging.ERROR
    CRITICAL = "CRITICAL", logging.CRITICAL

    def __init__(self, description: str, level: int):
        # pylint: disable=super-init-not-called
        self._description: str = description
        self._level: int = level

    @property
    def description(self) -> str:
        return self._description

    @property
    def level(self) -> int:
        return self._level


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    logger.configure(handlers=[{"sink": sys.stdout, "level": logging_level.level}])
