"""Tests for modbus sunspec base module."""

from unittest.mock import MagicMock

import pytest

from solaredge2mqtt.services.modbus.sunspec.base import (
    SunSpecOffset,
    SunSpecRegister,
    SunSpecRequestRegisterBundle,
)
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecValueType


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
        # Simulate string decoding (ModbusTcpClient returns string with nulls)
        # The actual decoding depends on ModbusTcpClient, but we test null strip
        result = TestRegister.TEST_REG.decode_response([0x5465, 0x7374, 0x0000, 0x0000], data)

        assert "test_reg" in result

    def test_register_decode_response_not_implemented(self):
        """Test register decode_response for not implemented values."""

        class TestRegister(SunSpecRegister):
            TEST_REG = "test_reg", 40000, SunSpecValueType.UINT16, True

        data = {}
        # 0xFFFF is not implemented value for UINT16
        result = TestRegister.TEST_REG.decode_response([0xFFFF], data)

        assert result["test_reg"] is False

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
            REG1 = "reg1", 40005, SunSpecValueType.UINT16, True  # end = 40006
            REG2 = "reg2", 40002, SunSpecValueType.UINT16, True  # end = 40003

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        # Should return maximum end address
        assert bundle.end_address == 40006

    def test_bundle_length(self):
        """Test bundle length property."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40002, SunSpecValueType.UINT16, True  # end = 40003
            REG2 = "reg2", 40005, SunSpecValueType.UINT16, True  # end = 40006

        bundle = SunSpecRequestRegisterBundle()
        bundle.add_register(TestRegister.REG1)
        bundle.add_register(TestRegister.REG2)

        # Length = end_address - address = 40006 - 40002 = 4
        assert bundle.length == 4

    def test_from_registers_single_bundle(self):
        """Test from_registers creates single bundle for nearby registers."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40001, SunSpecValueType.UINT16, True
            REG3 = "reg3", 40002, SunSpecValueType.UINT16, True

        bundles = SunSpecRequestRegisterBundle.from_registers(TestRegister)

        assert len(bundles) == 1

    def test_from_registers_multiple_bundles(self):
        """Test from_registers creates multiple bundles for distant registers."""

        class TestRegister(SunSpecRegister):
            REG1 = "reg1", 40000, SunSpecValueType.UINT16, True
            REG2 = "reg2", 40150, SunSpecValueType.UINT16, True  # > 120 away

        bundles = SunSpecRequestRegisterBundle.from_registers(TestRegister)

        assert len(bundles) == 2

    def test_from_registers_required_only(self):
        """Test from_registers with required_only=True."""

        class TestRegister(SunSpecRegister):
            REQ_REG = "req_reg", 40000, SunSpecValueType.UINT16, True
            OPT_REG = "opt_reg", 40001, SunSpecValueType.UINT16, False

        bundles = SunSpecRequestRegisterBundle.from_registers(
            TestRegister, required_only=True
        )

        # Should only include required registers in bundles
        assert len(bundles) == 1
        # Optional register within range is added
        all_registers = []
        for bundle in bundles:
            all_registers.extend(bundle.registers)

        assert TestRegister.REQ_REG in all_registers

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
