"""Tests for logging initialization module."""

import sys
from unittest.mock import MagicMock, patch

from solaredge2mqtt.core.logging import (
    _disable_pymodbus_stdout_logging,
    initialize_logging,
)
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
        assert len(handlers) == 1
        assert handlers[0]["sink"] is sys.stdout
        assert handlers[0]["level"] == LoggingLevelEnum.WARNING.level

    def test_disable_pymodbus_stdout_logging(self):
        """pymodbus logger should be silenced for stdout logging."""
        pymodbus_logger = MagicMock()
        with patch(
            "solaredge2mqtt.core.logging.logging.getLogger",
            return_value=pymodbus_logger,
        ):
            _disable_pymodbus_stdout_logging()

        pymodbus_logger.setLevel.assert_called_once()
        assert pymodbus_logger.propagate is False
        pymodbus_logger.handlers.clear.assert_called_once()
