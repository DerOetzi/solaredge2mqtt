"""Tests for homeassistant models module."""

import pytest
from pydantic import ValidationError

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantBaseModel,
    HomeAssistantBinarySensorType,
    HomeAssistantDevice,
    HomeAssistantEntity,
    HomeAssistantNumberType,
    HomeAssistantSelectType,
    HomeAssistantSensorType,
    HomeAssistantStatus,
    HomeAssistantStatusInput,
    HomeAssistantType,
)

STOREDGE_CONTROL_MODE_OPTIONS = {
    0: "Disabled",
    1: "Maximize Self Consumption",
    2: "Time of Use",
    3: "Backup Only",
    4: "Remote Control",
}


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
        input_model = HomeAssistantStatusInput.model_validate("online")

        assert input_model.status == HomeAssistantStatus.ONLINE

    def test_status_input_offline(self):
        """Test StatusInput with offline status."""
        input_model = HomeAssistantStatusInput.model_validate("offline")

        assert input_model.status == HomeAssistantStatus.OFFLINE

    def test_status_input_invalid(self):
        """Test StatusInput with invalid status."""

        with pytest.raises(ValidationError):
            HomeAssistantStatusInput.model_validate("invalid_status")


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

    def test_generic_number_type_field_kwargs(self):
        """Test GENERIC number type applies field() kwargs."""
        number = HomeAssistantNumberType.GENERIC

        assert number.typed == HomeAssistantType.NUMBER

        result = number.field(
            "Charge level",
            unit_of_measurement="%",
            min=0,
            max=100,
            step=100,
            mode="slider",
        )

        assert result["json_schema_extra"]["min"] == 0
        assert result["json_schema_extra"]["max"] == 100
        assert result["json_schema_extra"]["step"] == 100
        assert result["json_schema_extra"]["mode"] == "slider"
        assert result["json_schema_extra"]["unit_of_measurement"] == "%"


class TestHomeAssistantSelectType:
    """Tests for HomeAssistantSelectType enum."""

    def test_generic_select_type(self):
        """Test GENERIC select type properties."""
        select = HomeAssistantSelectType.GENERIC

        assert select.typed == HomeAssistantType.SELECT

    def test_field_includes_options_map(self):
        """Test field() injects options + options_map into json_schema_extra."""
        select = HomeAssistantSelectType.GENERIC
        options_map = {
            0: "Disabled",
            1: "Always Allowed",
            2: "Fixed Energy Limit",
            3: "Percent of Production",
        }

        result = select.field("Storage AC charge policy", options_map=options_map)

        assert result["json_schema_extra"]["options"] == list(options_map.values())
        assert result["json_schema_extra"]["options_map"] == options_map

    def test_field_without_options_map(self):
        """Test field() defaults to empty options list without options_map."""
        select = HomeAssistantSelectType.GENERIC

        result = select.field("Some select")

        assert result["json_schema_extra"]["options"] == []
        assert result["json_schema_extra"]["options_map"] is None


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

    def test_entity_device_class_override(self):
        """Test device_class_override takes precedence over ha_type.device_class."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Temperature",
            path=["temperature"],
            ha_type=HomeAssistantSensorType.TEMP_C,
            device_class_override="power",
        )

        assert HomeAssistantSensorType.TEMP_C.device_class == "temperature"
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
            ha_type=HomeAssistantNumberType.GENERIC,
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

    def test_entity_command_topic_without_path(self):
        """Test command_topic for NUMBER type."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power Limit",
            ha_type=HomeAssistantNumberType.GENERIC,
        )

        assert entity.command_topic == "solaredge/inverter"

    def test_entity_command_topic_uses_override(self):
        """Test command_topic prefers command_topic_override over the schema path."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/modbus/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Storage control mode",
            path=["storedge_control", "storage_control_mode"],
            ha_type=HomeAssistantSelectType.GENERIC,
            options_map=STOREDGE_CONTROL_MODE_OPTIONS,
            command_topic_override="storedge/control_mode",
        )

        assert entity.command_topic == "solaredge/modbus/inverter/storedge/control_mode"

    def test_entity_value_template_select_maps_int_to_label(self):
        """Test value_template wraps the path in a dict lookup for select types."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/modbus/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Storage control mode",
            path=["storedge_control", "storage_control_mode"],
            ha_type=HomeAssistantSelectType.GENERIC,
            options_map=STOREDGE_CONTROL_MODE_OPTIONS,
        )

        template = entity.value_template

        assert template is not None
        assert "value_json.storedge_control.storage_control_mode" in template
        assert "'Remote Control'" in template

    def test_entity_value_template_casts_lookup_to_string(self):
        """Regression: pydantic's JSON-schema serialization stringifies
        options_map keys ('4' not 4), but the raw MQTT payload holds a real
        int. Without casting the lookup value to string too, the dict
        lookup silently mismatches and HA shows the entity with no value."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/modbus/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Storage control mode",
            path=["storedge_control", "storage_control_mode"],
            ha_type=HomeAssistantSelectType.GENERIC,
            options_map=STOREDGE_CONTROL_MODE_OPTIONS,
        )

        template = entity.value_template

        assert template is not None
        assert "| string" in template
        assert "'4': 'Remote Control'" in template

    def test_entity_command_template_for_select(self):
        """Test command_template reverses the options map for select types."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/modbus/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Storage control mode",
            path=["storedge_control", "storage_control_mode"],
            ha_type=HomeAssistantSelectType.GENERIC,
            options_map=STOREDGE_CONTROL_MODE_OPTIONS,
        )

        template = entity.command_template

        assert template is not None
        assert "'Remote Control': '4'" in template
        assert "[value]" in template

    def test_entity_command_template_none_for_non_select(self):
        """Test command_template is None for non-select entity types."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/inverter",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=["power"],
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        assert entity.command_template is None

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
            ha_type=HomeAssistantNumberType.GENERIC,
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

    def test_entity_unique_id_without_value_template(self):
        """Test unique_id path where value_template is None."""
        device = HomeAssistantDevice(
            client_id="test_client",
            name="Test Device",
            state_topic="solaredge/powerflow",
        )

        entity = HomeAssistantEntity(
            device=device,
            name="Power",
            path=None,
            ha_type=HomeAssistantSensorType.POWER_W,
        )

        unique_id = entity.unique_id
        assert isinstance(unique_id, str)
        assert len(unique_id) == 10
