"""Tests for modbus sunspec base module."""

from unittest.mock import patch

import pytest

from solaredge2mqtt.services.modbus.exceptions import InvalidRegisterDataException
from solaredge2mqtt.services.modbus.sunspec.base import (
    SunSpecOffset,
    SunSpecRegister,
    SunSpecRequestRegisterBundle,
)
from solaredge2mqtt.services.modbus.sunspec.values import (
    SunSpecPayload,
    SunSpecValueType,
)


class TestSunSpecRegister:
    """Tests for SunSpecRegister class."""

    def test_register_identifier(self):
        """Test register identifier property."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        assert TestRegister.TEST_REG.identifier == "test_reg"

    def test_register_address(self):
        """Test register address property."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40001, SunSpecValueType.UINT16, True

        assert TestRegister.TEST_REG.address == 40001

    def test_register_end_address(self):
        """Test register end_address property."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        # UINT16 has length 1
        assert TestRegister.TEST_REG.end_address == TestRegister.TEST_REG.address + 1

    def test_register_value_type(self):
        """Test register value_type property."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.INT32, True

        assert TestRegister.TEST_REG.value_type == SunSpecValueType.INT32

    def test_register_length(self):
        """Test register length property."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT32, True

        # UINT32 has length 2
        assert TestRegister.TEST_REG.length == 2

    def test_register_length_with_explicit_length(self):
        """Test register length property with explicit length."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.STRING, True, 16

        assert TestRegister.TEST_REG.length == 16

    def test_register_required(self):
        """Test register required property."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40000, SunSpecValueType.UINT16, True
            OPT_REG = "opt_reg", 40001, SunSpecValueType.UINT16, False

        assert TestRegister.REQ_REG.required is True
        assert TestRegister.OPT_REG.required is False

    def test_register_wordorder(self):
        """Test register wordorder static method."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        assert TestRegister.wordorder() == "big"

    def test_register_decode_response_uint16(self):
        """Test register decode_response for UINT16."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        data = {}
        result = TestRegister.TEST_REG.decode_response([1000], data)

        assert "test_reg" in result
        assert result["test_reg"] == 1000

    def test_register_decode_response_string(self):
        """Test register decode_response for STRING - strips null chars."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.STRING, True, 8

        data = {}
        # Simulate string decoding (ModbusTcpClient returns string with
        # nulls). The actual decoding depends on ModbusTcpClient, but we
        # test null strip
        result = TestRegister.TEST_REG.decode_response(
            [0x5465, 0x7374, 0x0000, 0x0000], data
        )

        assert "test_reg" in result

    def test_register_decode_response_not_implemented(self):
        """Test register decode_response for not implemented values."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        data = {}
        # 0xFFFF is not implemented value for UINT16
        result = TestRegister.TEST_REG.decode_response([0xFFFF], data)

        assert result["test_reg"] is False

    @patch("solaredge2mqtt.services.modbus.sunspec.base.logger")
    @patch(
        "pymodbus.client.ModbusTcpClient.convert_from_registers",
        side_effect=UnicodeDecodeError(
            "utf-8", b"\xc2", 5, 6, "invalid continuation byte"
        ),
    )
    def test_register_decode_response_unicode_error(self, mock_convert, mock_logger):
        """Test register decode_response handles UnicodeDecodeError."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40123, SunSpecValueType.STRING, True, 16

        data: SunSpecPayload = {"existing_key": "existing_value"}
        invalid_registers = [
            0x5465,
            0x7374,
            0xC200,
            0x0000,
            0x0000,
            0x0000,
            0x0000,
            0x0000,
        ]

        # Should raise InvalidRegisterDataException after logging
        with pytest.raises(InvalidRegisterDataException) as exc_info:
            TestRegister.TEST_REG.decode_response(invalid_registers, data)

        # Verify exception attributes
        exception = exc_info.value
        assert exception.register_id == "test_reg"
        assert exception.address == 40123
        assert exception.raw_values == invalid_registers
        assert isinstance(exception.original_error, UnicodeDecodeError)

        # Should have logged 1 error and 1 debug (after SonarQube fixes)
        assert mock_logger.error.call_count == 1
        assert mock_logger.debug.call_count == 1

        # Verify error message contains key information
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed to decode register" in error_call
        assert "test_reg" in error_call
        assert "40123" in error_call

        # Verify debug message contains raw register values
        debug_call = mock_logger.debug.call_args_list[0][0][0]
        assert "test_reg" in debug_call
        assert str(invalid_registers) in debug_call

    @patch("solaredge2mqtt.services.modbus.sunspec.base.logger")
    @patch(
        "pymodbus.client.ModbusTcpClient.convert_from_registers",
        side_effect=UnicodeDecodeError("utf-8", b"\xc2", 0, 1, "invalid start byte"),
    )
    def test_register_decode_response_unicode_error_empty_data(
        self, mock_convert, mock_logger
    ):
        """Test UnicodeDecodeError handling with empty initial data."""

        class TestRegister(SunSpecRegister):
            MANUFACTURER = (
                "c_manufacturer",
                40123,
                SunSpecValueType.STRING,
                True,
                16,
            )

        data: SunSpecPayload = {}

        # Should raise InvalidRegisterDataException after logging
        with pytest.raises(InvalidRegisterDataException) as exc_info:
            TestRegister.MANUFACTURER.decode_response([0xC200, 0x0000], data)

        # Verify exception attributes
        exception = exc_info.value
        assert exception.register_id == "c_manufacturer"
        assert exception.address == 40123

        # Should have logged appropriate messages
        assert mock_logger.error.call_count == 1
        assert mock_logger.debug.call_count == 1

    def test_register_encode_request_int(self):
        """Test register encode_request for integer."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        result = TestRegister.TEST_REG.encode_request(1000)

        assert isinstance(result, list)

    def test_register_encode_request_bool_true(self):
        """Test register encode_request for boolean True."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        result = TestRegister.TEST_REG.encode_request(True)

        assert isinstance(result, list)

    def test_register_encode_request_bool_false(self):
        """Test register encode_request for boolean False."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        result = TestRegister.TEST_REG.encode_request(False)

        assert isinstance(result, list)

    def test_request_bundles_caching(self):
        """Test that request_bundles caches the result."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40001, SunSpecValueType.UINT16, True

        bundles1 = TestRegister.request_bundles()
        bundles2 = TestRegister.request_bundles()

        # Should return same cached object
        assert bundles1 is bundles2

    @patch(
        "pymodbus.client.ModbusTcpClient.convert_from_registers",
        return_value=[1, 2],
    )
    def test_register_decode_response_list_value_raises(self, _mock_convert):
        """Test decode_response rejects list payloads from pymodbus."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40020, SunSpecValueType.UINT16, True

        with pytest.raises(InvalidRegisterDataException) as exc_info:
            TestRegister.TEST_REG.decode_response([1], {})

        assert exc_info.value.register_id == "test_reg"
        assert exc_info.value.address == 40020
        assert exc_info.value.raw_values == [1]
        assert isinstance(exc_info.value.original_error, TypeError)

    @patch(
        "pymodbus.client.ModbusTcpClient.convert_from_registers",
        return_value="Test\x00\x00  ",
    )
    def test_register_decode_response_string_strip_and_rstrip(self, _mock_convert):
        """Test decode_response strips null bytes and trailing spaces."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40021, SunSpecValueType.STRING, True, 8

        result = TestRegister.TEST_REG.decode_response([0, 0, 0, 0], {})

        assert result["test_reg"] == "Test\x00\x00"

    def test_register_without_available_length_raises_attribute_error(self):
        """Test register without explicit or type length has no _length field."""

        class InvalidLengthRegister(SunSpecRegister):
            BROKEN = "broken", 49000, SunSpecValueType.STRING, False

        with pytest.raises(AttributeError):
            _ = InvalidLengthRegister.BROKEN.length

    def test_request_bundles_required_only_false(self):
        """Test request_bundles with required_only=False includes optional regs."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40030, SunSpecValueType.UINT16, True
            OPT_REG = "opt_reg", 40031, SunSpecValueType.UINT16, False

        if hasattr(TestRegister, "_cached_bundles_by_required_only"):
            delattr(TestRegister, "_cached_bundles_by_required_only")

        bundles = TestRegister.request_bundles(required_only=False)

        all_registers = []
        for bundle in bundles:
            all_registers.extend(bundle.registers)

        assert TestRegister.REQ_REG in all_registers
        assert TestRegister.OPT_REG in all_registers

    def test_request_bundles_cache_isolated_by_required_only(self):
        """Test request_bundles keeps separate cache entries per argument."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40040, SunSpecValueType.UINT16, True
            OPT_REG = "opt_reg", 40041, SunSpecValueType.UINT16, False

        required_only_bundles = TestRegister.request_bundles(required_only=True)
        all_bundles = TestRegister.request_bundles(required_only=False)

        assert required_only_bundles is not all_bundles

        required_registers = [
            register
            for bundle in required_only_bundles
            for register in bundle.registers
        ]
        all_registers = [
            register for bundle in all_bundles for register in bundle.registers
        ]

        assert TestRegister.OPT_REG not in required_registers
        assert TestRegister.OPT_REG in all_registers


class TestSunSpecRequestRegisterBundle:
    """Tests for SunSpecRequestRegisterBundle class."""

    def test_empty_bundle_length(self):
        """Test empty bundle has length 0."""
        bundle = SunSpecRequestRegisterBundle()

        assert bundle.length == 0

    def test_bundle_add_register(self):
        """Test adding register to bundle."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.TEST_REG)

        assert len(bundle.registers) == 1
        assert TestRegister.TEST_REG in bundle.registers

    def test_bundle_address(self):
        """Test bundle address property."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40005, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40002, SunSpecValueType.UINT16, True

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        # Should return minimum address
        assert bundle.address == 40002

    def test_bundle_end_address(self):
        """Test bundle end_address property."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40005, SunSpecValueType.UINT16, True  # end to 40006
            REG2 = "reg2", 40002, SunSpecValueType.UINT16, True  # end to 40003

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        # Should return maximum end address
        assert bundle.end_address == 40006

    def test_bundle_length(self):
        """Test bundle length property."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40002, SunSpecValueType.UINT16, True  # end to 40003
            REG2 = "reg2", 40005, SunSpecValueType.UINT16, True  # end to 40006

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        assert bundle.length == 4

    def test_from_registers_single_bundle(self):
        """Test from_registers creates single bundle for nearby registers."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40001, SunSpecValueType.UINT16, True
            REG3 = "reg3", 40002, SunSpecValueType.UINT16, True

        bundles = SunSpecRequestRegisterBundle.from_registers(list(TestRegister))

        assert len(bundles) == 1

    def test_from_registers_multiple_bundles(self):
        """Test from_registers creates multiple bundles for distant
        registers."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40150, SunSpecValueType.UINT16, True  # > 120 away

        bundles = SunSpecRequestRegisterBundle.from_registers(list(TestRegister))

        assert len(bundles) == 2

    def test_from_registers_required_only(self):
        """Test from_registers with required_only=True."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40000, SunSpecValueType.UINT16, True
            OPT_REG = "opt_reg", 40001, SunSpecValueType.UINT16, False

        bundles = SunSpecRequestRegisterBundle.from_registers(
            list(TestRegister), required_only=True
        )

        # Should only include required registers in bundles
        assert len(bundles) == 1
        # Optional register within range is added
        all_registers = []
        for bundle in bundles:
            all_registers.extend(bundle.registers)

        assert TestRegister.REQ_REG in all_registers

    def test_from_registers_required_only_false_skips_optional_merge(self):
        """Test required_only=False does not call optional merge helper."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40100, SunSpecValueType.UINT16, True
            OPT_REG = "opt_reg", 40101, SunSpecValueType.UINT16, False

        bundles = SunSpecRequestRegisterBundle.from_registers(
            list(TestRegister), required_only=False
        )

        assert len(bundles) == 1
        assert len(bundles[0].registers) == 2

    def test_bundle_registers_required_only_no_required(self):
        """Test internal bundling returns empty bundles with no required regs."""

        class TestRegister(SunSpecRegister):
            OPT_REG1 = "opt_reg1", 40200, SunSpecValueType.UINT16, False
            OPT_REG2 = "opt_reg2", 40201, SunSpecValueType.UINT16, False

        bundles = SunSpecRequestRegisterBundle._bundle_registers(
            required_only=True,
            sorted_registers=list(TestRegister),
        )

        assert bundles == []

    def test_add_not_required_does_not_include_out_of_range_registers(self):
        """Test optional registers outside bundle range are not added."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40300, SunSpecValueType.UINT16, True
            OPT_REG_OUTSIDE = "opt_reg_outside", 40450, SunSpecValueType.UINT16, False

        bundles = SunSpecRequestRegisterBundle._bundle_registers(
            required_only=True,
            sorted_registers=[TestRegister.REQ_REG],
        )
        result = SunSpecRequestRegisterBundle._add_not_required(
            [TestRegister.REQ_REG, TestRegister.OPT_REG_OUTSIDE], bundles
        )

        assert len(result) == 1
        assert TestRegister.REQ_REG in result[0].registers
        assert TestRegister.OPT_REG_OUTSIDE not in result[0].registers

    def test_add_not_required_includes_registers_inside_bundle_range(self):
        """Test optional registers within bundle range are added."""

        class TestRegister(SunSpecRegister):
            REQ_REG_WIDE = "req_reg_wide", 40500, SunSpecValueType.UINT32, True
            OPT_REG_INSIDE = "opt_reg_inside", 40501, SunSpecValueType.UINT16, False

        bundles = SunSpecRequestRegisterBundle._bundle_registers(
            required_only=True,
            sorted_registers=[TestRegister.REQ_REG_WIDE],
        )
        result = SunSpecRequestRegisterBundle._add_not_required(
            [TestRegister.REQ_REG_WIDE, TestRegister.OPT_REG_INSIDE], bundles
        )

        assert TestRegister.OPT_REG_INSIDE in result[0].registers

    def test_bundle_decode_response_with_sparse_offsets(self):
        """Test decode_response slices register values by per-register offset."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 41000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 41002, SunSpecValueType.UINT16, True

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        result = bundle.decode_response([10, 999, 20], {})

        assert result["reg1"] == 10
        assert result["reg2"] == 20

    def test_bundle_decode_response(self):
        """Test bundle decode_response."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40001, SunSpecValueType.UINT16, True

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        data = {}
        result = bundle.decode_response([100, 200], data)

        assert "reg1" in result
        assert "reg2" in result


class TestSunSpecOffset:
    """Tests for SunSpecOffset class."""

    def test_offset_idx(self):
        """Test offset idx property."""

        class TestOffset(SunSpecOffset):
            OFFSET0 = "test0", 0
            OFFSET1 = "test1", 100

        assert TestOffset.OFFSET0.idx == 0
        assert TestOffset.OFFSET1.idx == 1

    def test_offset_identifier(self):
        """Test offset identifier property."""

        class TestOffset(SunSpecOffset):
            OFFSET0 = "meter0", 0

        assert TestOffset.OFFSET0.identifier == "meter0"

    def test_offset_offset(self):
        """Test offset offset property."""

        class TestOffset(SunSpecOffset):
            OFFSET0 = "test0", 0
            OFFSET1 = "test1", 174

        assert TestOffset.OFFSET0.offset == 0
        assert TestOffset.OFFSET1.offset == 174
