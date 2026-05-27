"""Tests for logging initialization module."""

import logging
import sys
from unittest.mock import patch

from solaredge2mqtt.core.logging import (
    deregister_mqtt_log_sink,
    initialize_logging,
    register_mqtt_log_sink,
)
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

    def test_initialize_logging_suppresses_pymodbus(self):
        """initialize_logging should set pymodbus log level to CRITICAL."""
        initialize_logging(LoggingLevelEnum.DEBUG)
        pymodbus_logger = logging.getLogger("pymodbus")
        assert pymodbus_logger.level == logging.CRITICAL
        assert pymodbus_logger.propagate is False


class TestRegisterDeregisterMqttLogSink:
    """Tests for register/deregister MQTT log sink helpers."""

    def test_register_returns_int_handler_id(self, mock_event_bus):
        """register_mqtt_log_sink should return an integer handler id."""
        handler_id = register_mqtt_log_sink(mock_event_bus, LoggingLevelEnum.DEBUG)
        assert isinstance(handler_id, int)
        # Clean up
        deregister_mqtt_log_sink(handler_id)

    def test_deregister_removes_handler(self, mock_event_bus):
        """deregister_mqtt_log_sink should silently succeed even when called twice."""
        handler_id = register_mqtt_log_sink(mock_event_bus, LoggingLevelEnum.DEBUG)
        deregister_mqtt_log_sink(handler_id)
        # Second call should not raise
        deregister_mqtt_log_sink(handler_id)

    def test_deregister_with_none_does_not_raise(self):
        """deregister_mqtt_log_sink(None) should not raise."""
        deregister_mqtt_log_sink(None)

