"""Tests for homeassistant models module."""

import hashlib
import base64

import pytest

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBaseModel,
    HomeAssistantBinarySensorType,
    HomeAssistantDevice,
    HomeAssistantEntity,
    HomeAssistantEntityBaseType,
    HomeAssistantNumberType,
    HomeAssistantSensorType,
    HomeAssistantStatus,
    HomeAssistantStatusInput,
    HomeAssistantType,
)


class TestHomeAssistantStatus:
    """Tests for HomeAssistantStatus enum."""

    def test_online_status(self):
        """Test ONLINE status."""
        status = HomeAssistantStatus.ONLINE

        assert status.status == "online"
        assert str(status) == "online"

    def test_offline_status(self):
        """Test OFFLINE status."""
        status = HomeAssistantStatus.OFFLINE

        assert status.status == "offline"
        assert str(status) == "offline"


class TestHomeAssistantStatusInput:
    """Tests for HomeAssistantStatusInput class."""

    def test_status_input_online(self):
        """Test StatusInput with online status."""
        input_model = HomeAssistantStatusInput("online")

        assert input_model.status == HomeAssistantStatus.ONLINE

    def test_status_input_offline(self):
        """Test StatusInput with offline status."""
        input_model = HomeAssistantStatusInput("offline")

        assert input_model.status == HomeAssistantStatus.OFFLINE


class TestHomeAssistantBaseModel:
    """Tests for HomeAssistantBaseModel class."""

    def test_hash_unique_id(self):
        """Test hash_unique_id generates consistent hash."""
        model = HomeAssistantBaseModel(client_id="test_client")

        id1 = model.hash_unique_id(["id1", "id2"])
        id2 = model.hash_unique_id(["id1", "id2"])

        # Different calls with same input should produce same hash
        assert id1 == id2
        assert len(id1) == 10  # Base64 encoded, truncated to 10 chars

    def test_hash_unique_id_different_inputs(self):
        """Test hash_unique_id produces different results for different inputs."""
        model = HomeAssistantBaseModel(client_id="test_client")

        id1 = model.hash_unique_id(["id1"])
        id2 = model.hash_unique_id(["id2"])

        assert id1 != id2

    def test_hash_unique_id_includes_client_id(self):
        """Test hash_unique_id includes client_id in hash."""
        model1 = HomeAssistantBaseModel(client_id="client1")
        model2 = HomeAssistantBaseModel(client_id="client2")

        id1 = model1.hash_unique_id(["same_id"])
        id2 = model2.hash_unique_id(["same_id"])

        assert id1 != id2


class TestHomeAssistantType:
    """Tests for HomeAssistantType enum."""

    def test_binary_sensor_type(self):
        """Test BINARY_SENSOR type properties."""
        sensor_type = HomeAssistantType.BINARY_SENSOR

        assert sensor_type.identifier == "binary_sensor"
        assert sensor_type.command_topic is False
        assert sensor_type.additional_fields == []

    def test_number_type(self):
        """Test NUMBER type properties."""
        number_type = HomeAssistantType.NUMBER

        assert number_type.identifier == "number"
        assert number_type.command_topic is True
        assert "min" in number_type.additional_fields
        assert "max" in number_type.additional_fields
        assert "step" in number_type.additional_fields
        assert "mode" in number_type.additional_fields

    def test_sensor_type(self):
        """Test SENSOR type properties."""
        sensor_type = HomeAssistantType.SENSOR

        assert sensor_type.identifier == "sensor"
        assert sensor_type.command_topic is False
        assert sensor_type.additional_fields == []


class TestHomeAssistantBinarySensorType:
    """Tests for HomeAssistantBinarySensorType enum."""

    def test_enabled_type(self):
        """Test ENABLED binary sensor type."""
        sensor = HomeAssistantBinarySensorType.ENABLED

        assert sensor.typed == HomeAssistantType.BINARY_SENSOR
        assert sensor.device_class is None

    def test_grid_status_type(self):
        """Test GRID_STATUS binary sensor type."""
        sensor = HomeAssistantBinarySensorType.GRID_STATUS

        assert sensor.typed == HomeAssistantType.BINARY_SENSOR
        assert sensor.device_class == "power"

    def test_plug_type(self):
        """Test PLUG binary sensor type."""
        sensor = HomeAssistantBinarySensorType.PLUG

        assert sensor.typed == HomeAssistantType.BINARY_SENSOR
        assert sensor.device_class == "plug"


class TestHomeAssistantNumberType:
    """Tests for HomeAssistantNumberType enum."""

    def test_active_power_limit_type(self):
        """Test ACTIVE_POWER_LIMIT number type."""
        number = HomeAssistantNumberType.ACTIVE_POWER_LIMIT

        assert number.typed == HomeAssistantType.NUMBER
        assert number.unit_of_measurement == "%"
        assert number._min == 0
        assert number._max == 100
        assert number._step == 1
        assert number._mode == "slider"


class TestHomeAssistantSensorType:
    """Tests for HomeAssistantSensorType enum."""

    def test_power_w_type(self):
        """Test POWER_W sensor type."""
        sensor = HomeAssistantSensorType.POWER_W

        assert sensor.typed == HomeAssistantType.SENSOR
        assert sensor.device_class == "power"
        assert sensor.state_class == "measurement"
        assert sensor.unit_of_measurement == "W"

    def test_energy_kwh_type(self):
        """Test ENERGY_KWH sensor type."""
        sensor = HomeAssistantSensorType.ENERGY_KWH

        assert sensor.typed == HomeAssistantType.SENSOR
        assert sensor.device_class == "energy"
        assert sensor.state_class == "total_increasing"
        assert sensor.unit_of_measurement == "kWh"

    def test_battery_type(self):
        """Test BATTERY sensor type."""
        sensor = HomeAssistantSensorType.BATTERY

        assert sensor.typed == HomeAssistantType.SENSOR
        assert sensor.device_class == "battery"
        assert sensor.unit_of_measurement == "%"

    def test_temperature_type(self):
        """Test TEMP_C sensor type."""
        sensor = HomeAssistantSensorType.TEMP_C

        assert sensor.typed == HomeAssistantType.SENSOR
        assert sensor.device_class == "temperature"
        assert sensor.unit_of_measurement == "°C"

    def test_voltage_type(self):
        """Test VOLTAGE_V sensor type."""
        sensor = HomeAssistantSensorType.VOLTAGE_V

        assert sensor.device_class == "voltage"
        assert sensor.unit_of_measurement == "V"

    def test_current_type(self):
        """Test CURRENT_A sensor type."""
        sensor = HomeAssistantSensorType.CURRENT_A

        assert sensor.device_class == "current"
        assert sensor.unit_of_measurement == "A"

    def test_monetary_type(self):
        """Test MONETARY sensor type."""
        sensor = HomeAssistantSensorType.MONETARY

        assert sensor.device_class == "monetary"
        assert sensor.state_class == "total"

    def test_field_method(self):
        """Test field method generates correct dict."""
        sensor = HomeAssistantSensorType.POWER_W

        result = sensor.field("Test Power")

        assert result["title"] == "Test Power"
        assert "json_schema_extra" in result
        assert result["json_schema_extra"]["ha_type"] == sensor
        assert result["json_schema_extra"]["ha_typed"] == "sensor"

    def test_field_method_with_icon(self):
        """Test field method with icon."""
        sensor = HomeAssistantSensorType.POWER_W

        result = sensor.field("Test Power", icon="solar-power")

        assert result["json_schema_extra"]["icon"] == "solar-power"


class TestHomeAssistantDevice:
    """Tests for HomeAssistantDevice class."""

    def test_device_creation(self):
        """Test HomeAssistantDevice creation."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="test/topic",
            manufacturer="Test Manufacturer",
            model="Test Model",
        )

        assert device.name == "Test Device"
        assert device.manufacturer == "Test Manufacturer"
        assert device.model == "Test Model"

    def test_device_identifiers_computed(self):
        """Test identifiers computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="test/topic",
            manufacturer="Test Mfg",
            model="Test Model",
            serial_number="SN123",
        )

        identifiers = device.identifiers

        assert isinstance(identifiers, str)
        assert len(identifiers) == 10

    def test_device_identifiers_with_unit_key(self):
        """Test identifiers includes unit_key when present."""
        device1 = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="test/topic",
            manufacturer="Test Mfg",
            model="Test Model",
            serial_number="SN123",
        )

        device2 = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="test/topic",
            manufacturer="Test Mfg",
            model="Test Model",
            serial_number="SN123",
            unit_key="leader",
        )

        # Different identifiers due to unit_key
        assert device1.identifiers != device2.identifiers


class TestHomeAssistantEntity:
    """Tests for HomeAssistantEntity class."""

    def test_entity_creation(self):
        """Test HomeAssistantEntity creation."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["inverter", "power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.name == "Power"
        assert entity.device == device

    def test_entity_unique_id(self):
        """Test unique_id computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["inverter", "power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        unique_id = entity.unique_id

        assert isinstance(unique_id, str)
        assert len(unique_id) == 10

    def test_entity_state_topic(self):
        """Test state_topic computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["inverter", "power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.state_topic == "solaredge/powerflow"

    def test_entity_value_template(self):
        """Test value_template computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["inverter", "power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.value_template == "{{ value_json.inverter.power }}"

    def test_entity_value_template_no_path(self):
        """Test value_template is None when no path."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.value_template is None

    def test_entity_state_class(self):
        """Test state_class computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.state_class == "measurement"

    def test_entity_device_class(self):
        """Test device_class computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.device_class == "power"

    def test_entity_unit_of_measurement(self):
        """Test unit_of_measurement computed field."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.unit_of_measurement == "W"

    def test_entity_unit_of_measurement_override(self):
        """Test unit_of_measurement with custom unit."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Money",
            path=["money"],
            ha_type=HomeAssistantSensorType.MONETARY,
            unit="EUR",
        )

        assert entity.unit_of_measurement == "EUR"

    def test_entity_payload_on_binary_sensor(self):
        """Test payload_on for binary sensor."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Grid Status",
            path=["grid_status"],
            ha_type=HomeAssistantBinarySensorType.GRID_STATUS,
        )

        assert entity.payload_on is True
        assert entity.payload_off is False

    def test_entity_payload_on_non_binary_sensor(self):
        """Test payload_on is None for non-binary sensor."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.payload_on is None
        assert entity.payload_off is None

    def test_entity_icon_with_icon(self):
        """Test icon computed field with icon."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
            icon="solar-power",
        )

        assert entity.icon == "mdi:solar-power"

    def test_entity_icon_without_icon(self):
        """Test icon is None without icon."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.icon is None

    def test_entity_command_topic_for_number(self):
        """Test command_topic for NUMBER type."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power Limit",
            path=["power_limit"],
            ha_type=HomeAssistantNumberType.ACTIVE_POWER_LIMIT,
        )

        assert entity.command_topic == "solaredge/inverter/power_limit"

    def test_entity_command_topic_for_sensor(self):
        """Test command_topic is None for SENSOR type."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.command_topic is None

    def test_entity_model_dump_json(self):
        """Test model_dump_json includes additional fields."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power Limit",
            path=["power_limit"],
            ha_type=HomeAssistantNumberType.ACTIVE_POWER_LIMIT,
            min=0,
            max=100,
            step=1,
            mode="slider",
        )

        json_str = entity.model_dump_json()

        assert "min" in json_str
        assert "max" in json_str
        assert "step" in json_str
        assert "mode" in json_str
