import logging

from solaredge2mqtt.core.models import EnumModel


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
