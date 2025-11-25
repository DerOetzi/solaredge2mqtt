"""Tests for core logging models module."""

import logging

import pytest

from solaredge2mqtt.core.logging.models import LoggingLevelEnum


class TestLoggingLevelEnum:
    """Tests for LoggingLevelEnum class."""

    def test_debug_level(self):
        """Test DEBUG level attributes."""
        assert LoggingLevelEnum.DEBUG.description == "DEBUG"
        assert LoggingLevelEnum.DEBUG.level == logging.DEBUG

    def test_info_level(self):
        """Test INFO level attributes."""
        assert LoggingLevelEnum.INFO.description == "INFO"
        assert LoggingLevelEnum.INFO.level == logging.INFO

    def test_warning_level(self):
        """Test WARNING level attributes."""
        assert LoggingLevelEnum.WARNING.description == "WARNING"
        assert LoggingLevelEnum.WARNING.level == logging.WARNING

    def test_error_level(self):
        """Test ERROR level attributes."""
        assert LoggingLevelEnum.ERROR.description == "ERROR"
        assert LoggingLevelEnum.ERROR.level == logging.ERROR

    def test_critical_level(self):
        """Test CRITICAL level attributes."""
        assert LoggingLevelEnum.CRITICAL.description == "CRITICAL"
        assert LoggingLevelEnum.CRITICAL.level == logging.CRITICAL

    def test_all_levels_exist(self):
        """Test that all expected levels exist."""
        expected_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in expected_levels:
            assert hasattr(LoggingLevelEnum, level)

    def test_string_representation(self):
        """Test string representation of logging levels."""
        assert str(LoggingLevelEnum.DEBUG) == "DEBUG"
        assert str(LoggingLevelEnum.INFO) == "INFO"
        assert str(LoggingLevelEnum.WARNING) == "WARNING"
        assert str(LoggingLevelEnum.ERROR) == "ERROR"
        assert str(LoggingLevelEnum.CRITICAL) == "CRITICAL"

    def test_from_string(self):
        """Test creating LoggingLevelEnum from string."""
        assert LoggingLevelEnum.from_string("DEBUG") == LoggingLevelEnum.DEBUG
        assert LoggingLevelEnum.from_string("INFO") == LoggingLevelEnum.INFO
        assert LoggingLevelEnum.from_string("WARNING") == LoggingLevelEnum.WARNING
        assert LoggingLevelEnum.from_string("ERROR") == LoggingLevelEnum.ERROR
        assert LoggingLevelEnum.from_string("CRITICAL") == LoggingLevelEnum.CRITICAL

    def test_from_string_invalid(self):
        """Test from_string raises error for invalid level."""
        with pytest.raises(ValueError):
            LoggingLevelEnum.from_string("INVALID_LEVEL")
