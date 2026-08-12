"""Tests for logging initialization module."""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from solaredge2mqtt.core.logging import (
    InterceptHandler,
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
            patch("solaredge2mqtt.core.logging.logging.basicConfig"),
        ):
            initialize_logging(LoggingLevelEnum.WARNING)

        assert mock_get_logger.call_count == 1
        mock_configure.assert_called_once()
        handlers = mock_configure.call_args.kwargs["handlers"]
        assert len(handlers) == 1
        assert handlers[0]["sink"] is sys.stdout
        assert handlers[0]["level"] == LoggingLevelEnum.WARNING.level

    def test_initialize_logging_installs_intercept_handler(self):
        """initialize_logging must bridge stdlib logging into loguru."""
        with (
            patch("solaredge2mqtt.core.logging.logger.configure"),
            patch("solaredge2mqtt.core.logging.logging.getLogger"),
            patch("solaredge2mqtt.core.logging.logging.basicConfig") as mock_basic,
        ):
            initialize_logging(LoggingLevelEnum.INFO)

        mock_basic.assert_called_once()
        kwargs = mock_basic.call_args.kwargs
        assert kwargs["level"] == 0
        assert kwargs["force"] is True
        assert len(kwargs["handlers"]) == 1
        assert isinstance(kwargs["handlers"][0], InterceptHandler)

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


class TestInterceptHandler:
    """Tests for InterceptHandler, which forwards stdlib records to loguru."""

    @pytest.fixture
    def captured(self):
        """A list that receives every formatted message loguru emits."""
        from loguru import logger as loguru_logger

        messages: list[str] = []
        sink_id = loguru_logger.add(lambda message: messages.append(message), level=0)
        yield messages
        loguru_logger.remove(sink_id)

    def _make_record(
        self, level: int = logging.INFO, msg: str = "hello", args: tuple = ()
    ) -> logging.LogRecord:
        return logging.LogRecord(
            name="pvlearn.forecaster",
            level=level,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=args,
            exc_info=None,
        )

    def test_emit_forwards_message_and_arguments(self, captured: list[str]):
        InterceptHandler().emit(self._make_record(msg="hello %s", args=("world",)))

        assert len(captured) == 1
        assert "hello world" in captured[0]

    def test_emit_maps_known_level_name(self, captured: list[str]):
        InterceptHandler().emit(self._make_record(level=logging.WARNING, msg="careful"))

        assert "WARNING" in captured[0]

    def test_emit_falls_back_to_levelno_for_unknown_level_name(
        self, captured: list[str]
    ):
        """A LogRecord with a level name loguru doesn't know must not raise."""
        record = self._make_record(msg="custom level message")
        record.levelname = "TOTALLY_MADE_UP_LEVEL"

        InterceptHandler().emit(record)

        assert len(captured) == 1
        assert "custom level message" in captured[0]

    def test_emit_includes_exception_info(self, captured: list[str]):
        try:
            raise ValueError("boom")
        except ValueError:
            record = logging.LogRecord(
                name="pvlearn.forecaster",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="failed",
                args=None,
                exc_info=sys.exc_info(),
            )

        InterceptHandler().emit(record)

        assert len(captured) == 1
        assert "ValueError" in captured[0]
        assert "boom" in captured[0]
