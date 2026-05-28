"""Tests for logging initialization module."""

import sys
from unittest.mock import patch

from solaredge2mqtt.core.logging import initialize_logging
from solaredge2mqtt.core.logging.models import LoggingLevelEnum


class TestLoggingInit:
    """Tests for initialize_logging helper."""

    def test_initialize_logging_configures_stdout_handler(self):
        """initialize_logging should configure loguru with stdout sink and level."""
        with (
            patch("solaredge2mqtt.core.logging.logger.configure") as mock_configure,
            patch("solaredge2mqtt.core.logging.logging.getLogger") as mock_get_logger,
        ):
            initialize_logging(LoggingLevelEnum.WARNING)

        assert mock_get_logger.call_count == 1
        mock_configure.assert_called_once()
        handlers = mock_configure.call_args.kwargs["handlers"]
        assert handlers[0]["sink"] is sys.stdout
        assert handlers[0]["level"] == LoggingLevelEnum.WARNING.level
        assert callable(handlers[1]["sink"])
        assert handlers[1]["level"] == LoggingLevelEnum.WARNING.level
        assert callable(handlers[1]["filter"])
