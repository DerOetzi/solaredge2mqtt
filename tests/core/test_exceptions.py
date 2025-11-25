"""Tests for core exceptions module."""

import pytest

from solaredge2mqtt.core.exceptions import ConfigurationException, InvalidDataException


class TestConfigurationException:
    """Tests for ConfigurationException class."""

    def test_configuration_exception_attributes(self):
        """Test ConfigurationException stores component and message."""
        exc = ConfigurationException("MQTT", "Connection failed")

        assert exc.component == "MQTT"
        assert exc.message == "Connection failed"

    def test_configuration_exception_is_exception(self):
        """Test ConfigurationException is an Exception subclass."""
        exc = ConfigurationException("MQTT", "Connection failed")

        assert isinstance(exc, Exception)

    def test_configuration_exception_with_extra_args(self):
        """Test ConfigurationException with additional arguments."""
        exc = ConfigurationException("MQTT", "Connection failed", "extra_arg")

        assert exc.component == "MQTT"
        assert exc.message == "Connection failed"

    def test_configuration_exception_can_be_raised(self):
        """Test ConfigurationException can be raised and caught."""
        with pytest.raises(ConfigurationException) as excinfo:
            raise ConfigurationException("ModBus", "Invalid host")

        assert excinfo.value.component == "ModBus"
        assert excinfo.value.message == "Invalid host"


class TestInvalidDataException:
    """Tests for InvalidDataException class."""

    def test_invalid_data_exception_attributes(self):
        """Test InvalidDataException stores message."""
        exc = InvalidDataException("Invalid modbus data")

        assert exc.message == "Invalid modbus data"

    def test_invalid_data_exception_is_exception(self):
        """Test InvalidDataException is an Exception subclass."""
        exc = InvalidDataException("Data validation failed")

        assert isinstance(exc, Exception)

    def test_invalid_data_exception_with_extra_args(self):
        """Test InvalidDataException with additional arguments."""
        exc = InvalidDataException("Invalid data", "extra_info")

        assert exc.message == "Invalid data"

    def test_invalid_data_exception_can_be_raised(self):
        """Test InvalidDataException can be raised and caught."""
        with pytest.raises(InvalidDataException) as exc_info:
            raise InvalidDataException("Powerflow data invalid")

        assert exc_info.value.message == "Powerflow data invalid"
