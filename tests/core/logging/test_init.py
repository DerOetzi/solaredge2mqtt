"""Tests for logging initialization module."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from solaredge2mqtt.core.logging import (
    _disable_pymodbus_stdout_logging,
    _mqtt_logging_sink,
    configure_mqtt_logging,
    initialize_logging,
)
from solaredge2mqtt.core.logging.models import LoggingLevelEnum
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent


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

    def test_mqtt_log_filter(self):
        """MQTT log filter should suppress configured MQTT warning/error records."""
        import logging as stdlib_logging

        configure_mqtt_logging(False)
        assert (
            _mqtt_logging_sink.log_filter(
                {"name": "x", "level": SimpleNamespace(name="INFO", no=20)}
            )
            is False
        )

        # Default min level is ERROR - messages below ERROR are filtered
        configure_mqtt_logging(True)
        assert (
            _mqtt_logging_sink.log_filter(
                {
                    "name": "solaredge2mqtt.service",
                    "level": SimpleNamespace(name="INFO", no=20),
                }
            )
            is False  # INFO (20) is below ERROR (40) threshold
        )
        # ERROR level from non-MQTT source passes through
        assert (
            _mqtt_logging_sink.log_filter(
                {
                    "name": "solaredge2mqtt.service",
                    "level": SimpleNamespace(name="ERROR", no=40),
                }
            )
            is True
        )
        assert (
            _mqtt_logging_sink.log_filter(
                {
                    "name": "solaredge2mqtt.core.mqtt.test",
                    "level": SimpleNamespace(name="ERROR", no=40),
                }
            )
            is False
        )
        # MQTT module warnings/errors are suppressed to avoid recursion
        assert (
            _mqtt_logging_sink.log_filter(
                {
                    "name": "solaredge2mqtt.core.mqtt.test",
                    "level": SimpleNamespace(name="WARNING", no=30),
                }
            )
            is False
        )

        # With INFO level configured, INFO passes through
        configure_mqtt_logging(True, stdlib_logging.INFO)
        assert (
            _mqtt_logging_sink.log_filter(
                {
                    "name": "solaredge2mqtt.service",
                    "level": SimpleNamespace(name="INFO", no=20),
                }
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_mqtt_log_sink_emits_mqtt_publish_event(self, mock_event_bus):
        """MQTT log sink should emit a logging topic publish event."""
        message = SimpleNamespace(
            record={
                "time": SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
                "level": SimpleNamespace(name="INFO"),
                "message": "hello",
            }
        )

        _mqtt_logging_sink.sink(message)
        await asyncio.sleep(0)

        mock_event_bus.emit.assert_awaited_once()
        event = mock_event_bus.emit.call_args.args[0]
        assert isinstance(event, MQTTPublishEvent)
        assert event.topic == "logging"
        assert event.payload == "2026-01-01T00:00:00 | INFO | hello"

    def test_mqtt_log_sink_returns_none_outside_event_loop(self):
        """MQTT log sink should return None when called outside async context."""
        message = SimpleNamespace(
            record={
                "time": SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
                "level": SimpleNamespace(name="INFO"),
                "message": "hello",
            }
        )

        result = _mqtt_logging_sink.sink(message)
        assert result is None
