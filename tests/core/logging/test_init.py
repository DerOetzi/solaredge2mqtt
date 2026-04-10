"""Tests for logging initialization module."""

import sys
from unittest.mock import patch

from solaredge2mqtt.core.logging import initialize_logging
from solaredge2mqtt.core.logging.models import LoggingLevelEnum


class TestLoggingInit:
    """Tests for initialize_logging helper."""

    def test_initialize_logging_configures_stdout_handler(self):
        """initialize_logging should configure loguru with stdout sink and level."""
        with patch("solaredge2mqtt.core.logging.logger.configure") as mock_configure:
            initialize_logging(LoggingLevelEnum.WARNING)

        mock_configure.assert_called_once_with(
            handlers=[
                {
                    "sink": sys.stdout,
                    "level": LoggingLevelEnum.WARNING.level,
                }
            ]
        )
