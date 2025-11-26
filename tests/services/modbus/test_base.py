"""Tests for modbus base models module."""


from solaredge2mqtt.services.modbus.models.base import (
    ModbusComponent,
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)


class TestModbusUnitRole:
    """Tests for ModbusUnitRole enum."""

    def test_unit_role_leader(self):
        """Test LEADER role."""
        assert str(ModbusUnitRole.LEADER) == "leader"
        assert ModbusUnitRole.LEADER.role == "leader"

    def test_unit_role_follower(self):
        """Test FOLLOWER role."""
        assert str(ModbusUnitRole.FOLLOWER) == "follower"
        assert ModbusUnitRole.FOLLOWER.role == "follower"

    def test_unit_role_cumulated(self):
        """Test CUMULATED role."""
        assert str(ModbusUnitRole.CUMULATED) == "cumulated"
        assert ModbusUnitRole.CUMULATED.role == "cumulated"


class TestModbusUnitInfo:
    """Tests for ModbusUnitInfo class."""

    def test_unit_info_creation(self):
        """Test ModbusUnitInfo creation."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )

        assert unit_info.unit == 1
        assert unit_info.key == "leader"
        assert unit_info.role == ModbusUnitRole.LEADER


class TestModbusDeviceInfo:
    """Tests for ModbusDeviceInfo class."""

    def test_device_info_basic(self):
        """Test ModbusDeviceInfo basic creation."""
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo(data)

        assert info.manufacturer == "SolarEdge"
        assert info.model == "SE10K"
        assert info.version == "1.0.0"
        assert info.serialnumber == "INV12345"
        assert info.sunspec_type == "Unknown"
        assert info.option is None
        assert info.unit is None

    def test_device_info_with_sunspec_did(self):
        """Test ModbusDeviceInfo with known sunspec DID."""
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "c_sunspec_did": 103,
        }

        info = ModbusDeviceInfo(data)

        assert info.sunspec_type == "Three Phase Inverter"

    def test_device_info_with_option(self):
        """Test ModbusDeviceInfo with option."""
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "c_option": "Export",
        }

        info = ModbusDeviceInfo(data)

        assert info.option == "Export"

    def test_device_info_with_unit(self):
        """Test ModbusDeviceInfo with unit."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "unit": unit_info,
        }

        info = ModbusDeviceInfo(data)

        assert info.unit is not None
        assert info.unit.key == "leader"

    def test_device_info_has_unit_true(self):
        """Test has_unit returns True when unit is present."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "unit": unit_info,
        }

        info = ModbusDeviceInfo(data)

        assert info.has_unit is True

    def test_device_info_has_unit_false(self):
        """Test has_unit returns False when unit is not present."""
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo(data)

        assert info.has_unit is False

    def test_device_info_unit_key_with_unit(self):
        """Test unit_key returns correct string when unit is present."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "unit": unit_info,
        }

        info = ModbusDeviceInfo(data)

        assert info.unit_key() == "leader"
        assert info.unit_key("_test") == "leader_test"

    def test_device_info_unit_key_without_unit(self):
        """Test unit_key returns empty string when unit is not present."""
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo(data)

        assert info.unit_key() == ""
        assert info.unit_key("_test") == ""

    def test_device_info_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo(data)
        ha_info = info.homeassistant_device_info("Inverter")

        assert ha_info["name"] == "SolarEdge Inverter"
        assert ha_info["manufacturer"] == "SolarEdge"
        assert ha_info["model"] == "SE10K"
        assert ha_info["hw_version"] == "1.0.0"
        assert ha_info["serial_number"] == "INV12345"

    def test_device_info_homeassistant_device_info_with_unit(self):
        """Test homeassistant_device_info includes unit_key when unit present."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "unit": unit_info,
        }

        info = ModbusDeviceInfo(data)
        ha_info = info.homeassistant_device_info("Inverter")

        assert ha_info["unit_key"] == "leader"

    def test_device_info_all_sunspec_did_types(self):
        """Test all known sunspec DID types."""
        sunspec_map = {
            101: "Single Phase Inverter",
            102: "Split Phase Inverter",
            103: "Three Phase Inverter",
            201: "Single Phase Meter",
            202: "Split Phase Meter",
            203: "Wye 3P1N Three Phase Meter",
            204: "Delta 3P Three Phase Meter",
            802: "Battery",
            803: "Lithium Ion Bank Battery",
            804: "Lithium Ion String Battery",
            805: "Lithium Ion Module Battery",
            806: "Flow Battery",
            807: "Flow String Battery",
            808: "Flow Module Battery",
            809: "Flow Stack Battery",
        }

        for did, expected_type in sunspec_map.items():
            data = {
                "c_manufacturer": "SolarEdge",
                "c_model": "Test",
                "c_version": "1.0",
                "c_serialnumber": "TEST123",
                "c_sunspec_did": did,
            }
            info = ModbusDeviceInfo(data)
            assert info.sunspec_type == expected_type


class TestModbusComponent:
    """Tests for ModbusComponent class."""

    def test_component_generate_topic_prefix_without_unit(self):
        """Test generate_topic_prefix without unit key."""

        class TestComponent(ModbusComponent):
            COMPONENT = "test"

        topic = TestComponent.generate_topic_prefix()
        assert topic == "modbus/test"

    def test_component_generate_topic_prefix_with_unit(self):
        """Test generate_topic_prefix with unit key."""

        class TestComponent(ModbusComponent):
            COMPONENT = "test"

        topic = TestComponent.generate_topic_prefix("leader")
        assert topic == "modbus/leader/test"
