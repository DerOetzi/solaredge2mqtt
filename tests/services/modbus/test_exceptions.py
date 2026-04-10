import pytest

from solaredge2mqtt.services.modbus.exceptions import InvalidRegisterDataException


class TestInvalidRegisterDataException:
    """Tests for InvalidRegisterDataException class."""

    def test_invalid_register_data_exception_attributes(self):
        """Test InvalidRegisterDataException stores all attributes."""
        original_err = UnicodeDecodeError(
            "utf-8", b"\xc2", 5, 6, "invalid continuation byte"
        )
        exc = InvalidRegisterDataException(
            register_id="c_manufacturer",
            address=40123,
            raw_values=[0x5465, 0x7374, 0xC200],
            original_error=original_err,
        )

        assert exc.register_id == "c_manufacturer"
        assert exc.address == 40123
        assert exc.raw_values == [0x5465, 0x7374, 0xC200]
        assert exc.original_error == original_err

    def test_invalid_register_data_exception_message(self):
        """Test InvalidRegisterDataException generates correct message."""
        original_err = ValueError("Test error")
        exc = InvalidRegisterDataException(
            register_id="test_reg",
            address=40000,
            raw_values=[0x1234],
            original_error=original_err,
        )

        expected_msg = (
            "Invalid data in register 'test_reg' at address 40000: Test error"
        )
        assert str(exc) == expected_msg

    def test_invalid_register_data_exception_is_exception(self):
        """Test InvalidRegisterDataException is an Exception subclass."""
        exc = InvalidRegisterDataException(
            register_id="test",
            address=1,
            raw_values=[],
            original_error=Exception("test"),
        )

        assert isinstance(exc, Exception)

    def test_invalid_register_data_exception_can_be_raised(self):
        """Test InvalidRegisterDataException can be raised and caught."""
        unicode_err = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid byte")

        with pytest.raises(InvalidRegisterDataException) as exc_info:
            raise InvalidRegisterDataException(
                register_id="c_model",
                address=40139,
                raw_values=[0xFFFF, 0x0000],
                original_error=unicode_err,
            )

        assert exc_info.value.register_id == "c_model"
        assert exc_info.value.address == 40139
        assert exc_info.value.raw_values == [0xFFFF, 0x0000]
        assert isinstance(exc_info.value.original_error, UnicodeDecodeError)

    def test_invalid_register_data_exception_preserves_cause(self):
        """Test InvalidRegisterDataException preserves exception chain."""
        original_err = UnicodeDecodeError("utf-8", b"\xc2", 0, 1, "test")

        try:
            try:
                raise original_err
            except UnicodeDecodeError as e:
                raise InvalidRegisterDataException(
                    register_id="test",
                    address=1,
                    raw_values=[],
                    original_error=e,
                ) from e
        except InvalidRegisterDataException as exc:
            assert exc.__cause__ == original_err
            assert exc.original_error == original_err
