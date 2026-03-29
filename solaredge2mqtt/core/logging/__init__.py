import sys

from loguru import logger

from solaredge2mqtt.core.logging.models import LoggingLevelEnum


def initialize_logging(logging_level: LoggingLevelEnum) -> None:
    logger.configure(handlers=[{"sink": sys.stdout, "level": logging_level.level}])
