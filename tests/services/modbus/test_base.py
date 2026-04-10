"""Tests for modbus base models module."""

import sys
import types

import pytest

from solaredge2mqtt.services.modbus.models.base import (
    ModbusComponent,
    ModbusDeviceInfo,
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecPayload


def _ensure_influx_point_stub() -> None:
    """Provide a local fallback for influx Point import during test collection."""

    influx_module = sys.modules.setdefault(
        "influxdb_client", types.ModuleType("influxdb_client")
    )
    client_module = sys.modules.setdefault(
        "influxdb_client.client", types.ModuleType("influxdb_client.client")
    )
    write_module = sys.modules.setdefault(
        "influxdb_client.client.write", types.ModuleType("influxdb_client.client.write")
    )

    point_module = types.ModuleType("influxdb_client.client.write.point")

    class Point: ...  # pragma: no cover

    setattr(point_module, "Point", Point)
    sys.modules["influxdb_client.client.write.point"] = point_module

    setattr(influx_module, "client", client_module)
    setattr(client_module, "write", write_module)
    setattr(write_module, "point", point_module)


try:
    from influxdb_client.client.write.point import Point as _InfluxPoint  # noqa: F401
except ImportError:
    _ensure_influx_point_stub()


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
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data)

        assert info.manufacturer == "SolarEdge"
        assert info.model == "SE10K"
        assert info.version == "1.0.0"
        assert info.serialnumber == "INV12345"
        assert info.sunspec_type == "Unknown"
        assert info.option is None
        assert info.unit is None

    def test_device_info_with_sunspec_did(self):
        """Test ModbusDeviceInfo with known sunspec DID."""
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "c_sunspec_did": 103,
        }

        info = ModbusDeviceInfo.from_sunspec(data)

        assert info.sunspec_type == "Three Phase Inverter"

    def test_device_info_with_option(self):
        """Test ModbusDeviceInfo with option."""
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
            "c_option": "Export",
        }

        info = ModbusDeviceInfo.from_sunspec(data)

        assert info.option == "Export"

    def test_device_info_with_unit(self):
        """Test ModbusDeviceInfo with unit."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data, unit_info)

        assert info.unit is not None
        assert info.unit.key == "leader"

    def test_device_info_has_unit_true(self):
        """Test has_unit returns True when unit is present."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data, unit_info)

        assert info.unit is not None

    def test_device_info_has_unit_false(self):
        """Test has_unit returns False when unit is not present."""
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data)

        assert info.unit is None

    def test_device_info_unit_key_with_unit(self):
        """Test unit_key returns correct string when unit is present."""
        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data, unit_info)

        assert info.unit_key() == "leader"
        assert info.unit_key("_test") == "leader_test"

    def test_device_info_unit_key_without_unit(self):
        """Test unit_key returns empty string when unit is not present."""
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data)

        assert info.unit_key() == ""
        assert info.unit_key("_test") == ""

    def test_device_info_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data)
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
        data: SunSpecPayload = {
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        }

        info = ModbusDeviceInfo.from_sunspec(data, unit_info)
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
            data: SunSpecPayload = {
                "c_manufacturer": "SolarEdge",
                "c_model": "Test",
                "c_version": "1.0",
                "c_serialnumber": "TEST123",
                "c_sunspec_did": did,
            }
            info = ModbusDeviceInfo.from_sunspec(data)
            assert info.sunspec_type == expected_type


class TestModbusComponent:
    """Tests for ModbusComponent class."""

    class DummyComponent(ModbusComponent):
        """Concrete test component for base class behavior."""

        COMPONENT = "dummy"
        value: int

        @classmethod
        def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, int]:
            return {"value": int(payload["value"])}

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

    def test_component_model_dump_influxdb(self):
        """Test model_dump_influxdb excludes info by default."""
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        # Create a real ModbusComponent subclass instance
        device_info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Meter",
                "c_version": "1.0.0",
                "c_serialnumber": "MTR12345",
            }
        )

        meter_data: SunSpecPayload = {
            "current": 10,
            "l1_current": 10,
            "current_scale": 0,
            "l1_voltage": 230,
            "l1n_voltage": 230,
            "voltage_scale": 0,
            "frequency": 50,
            "frequency_scale": 0,
            "power": 500,
            "power_scale": 0,
            "power_apparent": 550,
            "power_apparent_scale": 0,
            "power_reactive": 50,
            "power_reactive_scale": 0,
            "power_factor": 95,
            "power_factor_scale": -2,
            "export_energy_active": 10000,
            "import_energy_active": 5000,
            "energy_active_scale": 0,
        }

        meter = ModbusMeter.from_sunspec(device_info, meter_data)
        dumped = meter.model_dump_influxdb()

        # info should be excluded
        assert "info" not in dumped
        assert "info_manufacturer" not in dumped

    def test_component_model_json_schema_excludes_info(self):
        """Test model_json_schema excludes info."""
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        schema = ModbusMeter.model_json_schema()

        assert "info" not in schema.get("properties", {})

    def test_component_influxdb_tags(self):
        """Test influxdb_tags returns correct tags."""
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        device_info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Meter",
                "c_version": "1.0.0",
                "c_serialnumber": "MTR12345",
                "c_option": "Export+Import",
                "c_sunspec_did": 203,
            }
        )

        meter_data: SunSpecPayload = {
            "current": 10,
            "l1_current": 10,
            "current_scale": 0,
            "l1_voltage": 230,
            "l1n_voltage": 230,
            "voltage_scale": 0,
            "frequency": 50,
            "frequency_scale": 0,
            "power": 500,
            "power_scale": 0,
            "power_apparent": 550,
            "power_apparent_scale": 0,
            "power_reactive": 50,
            "power_reactive_scale": 0,
            "power_factor": 95,
            "power_factor_scale": -2,
            "export_energy_active": 10000,
            "import_energy_active": 5000,
            "energy_active_scale": 0,
        }

        meter = ModbusMeter.from_sunspec(device_info, meter_data)
        tags = meter.influxdb_tags

        assert tags["manufacturer"] == "SolarEdge"
        assert tags["model"] == "Meter"
        assert tags["serialnumber"] == "MTR12345"
        assert tags["option"] == "Export+Import"
        assert tags["sunspec_type"] == "Wye 3P1N Three Phase Meter"

    def test_component_mqtt_topic_without_followers(self):
        """Test mqtt_topic without followers."""
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        device_info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Meter",
                "c_version": "1.0.0",
                "c_serialnumber": "MTR12345",
            }
        )

        meter_data: SunSpecPayload = {
            "current": 10,
            "l1_current": 10,
            "current_scale": 0,
            "l1_voltage": 230,
            "l1n_voltage": 230,
            "voltage_scale": 0,
            "frequency": 50,
            "frequency_scale": 0,
            "power": 500,
            "power_scale": 0,
            "power_apparent": 550,
            "power_apparent_scale": 0,
            "power_reactive": 50,
            "power_reactive_scale": 0,
            "power_factor": 95,
            "power_factor_scale": -2,
            "export_energy_active": 10000,
            "import_energy_active": 5000,
            "energy_active_scale": 0,
        }

        meter = ModbusMeter.from_sunspec(device_info, meter_data)
        topic = meter.mqtt_topic(has_followers=False)

        assert topic == "modbus/meter"

    def test_component_mqtt_topic_with_followers(self):
        """Test mqtt_topic with followers."""
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        unit_info = ModbusUnitInfo(
            unit=1,
            key="leader",
            role=ModbusUnitRole.LEADER,
        )

        device_info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Meter",
                "c_version": "1.0.0",
                "c_serialnumber": "MTR12345",
            },
            unit_info,
        )

        meter_data: SunSpecPayload = {
            "current": 10,
            "l1_current": 10,
            "current_scale": 0,
            "l1_voltage": 230,
            "l1n_voltage": 230,
            "voltage_scale": 0,
            "frequency": 50,
            "frequency_scale": 0,
            "power": 500,
            "power_scale": 0,
            "power_apparent": 550,
            "power_apparent_scale": 0,
            "power_reactive": 50,
            "power_reactive_scale": 0,
            "power_factor": 95,
            "power_factor_scale": -2,
            "export_energy_active": 10000,
            "import_energy_active": 5000,
            "energy_active_scale": 0,
        }

        meter = ModbusMeter.from_sunspec(device_info, meter_data)
        topic = meter.mqtt_topic(has_followers=True)

        assert topic == "modbus/leader/meter"

    def test_component_has_unit_property(self):
        """Test has_unit property."""
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        # Without unit
        device_info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Meter",
                "c_version": "1.0.0",
                "c_serialnumber": "MTR12345",
            }
        )

        meter_data: SunSpecPayload = {
            "current": 10,
            "l1_current": 10,
            "current_scale": 0,
            "l1_voltage": 230,
            "l1n_voltage": 230,
            "voltage_scale": 0,
            "frequency": 50,
            "frequency_scale": 0,
            "power": 500,
            "power_scale": 0,
            "power_apparent": 550,
            "power_apparent_scale": 0,
            "power_reactive": 50,
            "power_reactive_scale": 0,
            "power_factor": 95,
            "power_factor_scale": -2,
            "export_energy_active": 10000,
            "import_energy_active": 5000,
            "energy_active_scale": 0,
        }

        meter = ModbusMeter.from_sunspec(device_info, meter_data)

        assert meter.info.unit is None

    def test_component_from_sunspec_uses_extractor(self):
        """Test generic from_sunspec calls class extractor and builds model."""

        info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Dummy",
                "c_version": "1.0.0",
                "c_serialnumber": "DUMMY123",
            }
        )

        component = self.DummyComponent.from_sunspec(info, {"value": 7})

        assert component.info == info
        assert component.value == 7

    def test_component_model_dump_influxdb_with_extra_exclude(self):
        """Test model dump excludes info and caller provided fields."""

        info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Dummy",
                "c_version": "1.0.0",
                "c_serialnumber": "DUMMY123",
            }
        )

        component = self.DummyComponent(info=info, value=9)
        dumped = component.model_dump_influxdb(exclude={"value"})

        assert "info" not in dumped
        assert "value" not in dumped

    def test_component_influxdb_tags_without_option(self):
        """Test influx tags omit option when no option is configured."""

        info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Dummy",
                "c_version": "1.0.0",
                "c_serialnumber": "DUMMY123",
            }
        )

        component = self.DummyComponent(info=info, value=1)
        tags = component.influxdb_tags

        assert tags["manufacturer"] == "SolarEdge"
        assert tags["model"] == "Dummy"
        assert tags["serialnumber"] == "DUMMY123"
        assert "option" not in tags

    def test_component_mqtt_topic_with_followers_but_without_unit(self):
        """Test follower topic path falls back to component topic when no unit."""

        info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Dummy",
                "c_version": "1.0.0",
                "c_serialnumber": "DUMMY123",
            }
        )

        component = self.DummyComponent(info=info, value=1)

        assert component.mqtt_topic(has_followers=True) == "modbus/dummy"

    def test_component_homeassistant_device_info_not_implemented(self):
        """Test base component homeassistant method raises by design."""

        info = ModbusDeviceInfo.from_sunspec(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Dummy",
                "c_version": "1.0.0",
                "c_serialnumber": "DUMMY123",
            }
        )

        component = self.DummyComponent(info=info, value=1)

        with pytest.raises(NotImplementedError, match="Not used in ModbusComponent"):
            component.homeassistant_device_info()

    def test_component_generate_topic_prefix_without_component_name(self):
        """Test topic prefix generation when component is an empty string."""

        class EmptyComponent(ModbusComponent):
            COMPONENT = ""

            @classmethod
            def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, int]:
                return {"value": 1}

        assert EmptyComponent.generate_topic_prefix() == "modbus/"


def test_modbus_component_extract_sunspec_payload_base_returns_none():
    """Test abstract base class method body executes pass statement."""

    assert ModbusComponent.extract_sunspec_payload({}) is None
