"""Tests for core models module."""

from datetime import datetime, timezone

import pytest

from solaredge2mqtt.core.models import (
    BaseField,
    BaseInputField,
    BaseInputFieldEnumModel,
    BaseInputScalarField,
    EnumModel,
    Solaredge2MQTTBaseModel,
)


class TestEnumModel:
    """Tests for EnumModel class."""

    def test_enum_model_string_representation(self):
        """Test that EnumModel returns correct string representation."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"
            VALUE_B = "value_b"

        assert str(TestEnum.VALUE_A) == "value_a"
        assert str(TestEnum.VALUE_B) == "value_b"

    def test_enum_model_repr(self):
        """Test that EnumModel returns correct repr."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"

        assert repr(TestEnum.VALUE_A) == "value_a"

    def test_enum_model_equality(self):
        """Test that EnumModel equality comparison works."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"
            VALUE_B = "value_b"

        value_a_copy = TestEnum.VALUE_A
        assert TestEnum.VALUE_A == value_a_copy
        assert TestEnum.VALUE_A != TestEnum.VALUE_B
        assert TestEnum.VALUE_A != "value_a"

    def test_enum_model_hash(self):
        """Test that EnumModel is hashable."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"
            VALUE_B = "value_b"

        enum_set = {TestEnum.VALUE_A, TestEnum.VALUE_B}
        assert len(enum_set) == 2
        assert TestEnum.VALUE_A in enum_set

    def test_enum_model_from_string(self):
        """Test that EnumModel can be created from string."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"
            VALUE_B = "value_b"

        assert TestEnum.from_string("value_a") == TestEnum.VALUE_A
        assert TestEnum.from_string("value_b") == TestEnum.VALUE_B

    def test_enum_model_from_string_invalid(self):
        """Test that EnumModel raises error for invalid string."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"

        with pytest.raises(ValueError) as exc_info:
            TestEnum.from_string("invalid_value")

        assert "No enum value invalid_value found" in str(exc_info.value)

    def test_enum_model_serialize(self):
        """Test that EnumModel serializes correctly."""

        class TestEnum(EnumModel):
            VALUE_A = "value_a"

        assert TestEnum.VALUE_A.serialize() == "value_a"


class TestBaseInputField:
    """Tests for BaseInputField class."""

    def test_base_input_field_forbids_extra(self):
        """Test that BaseInputField forbids extra fields."""

        class TestInput(BaseInputField):
            field1: str

        with pytest.raises(Exception):
            TestInput(
                field1="value",
                extra_field="should_fail",  # pyright: ignore[reportCallIssue]
            )

    def test_base_input_field_valid(self):
        """Test that BaseInputField accepts valid fields."""

        class TestInput(BaseInputField):
            field1: str
            field2: int = 0

        model = TestInput(field1="value", field2=42)
        assert model.field1 == "value"
        assert model.field2 == 42


class TestBaseInputScalarField:
    """Tests for BaseInputScalarField class."""

    def test_scalar_value_is_wrapped(self):
        """Scalar values are wrapped into single-field dicts."""

        class ScalarInput(BaseInputScalarField):
            value: int

        parsed = ScalarInput.model_validate(7)

        assert parsed.value == 7

    def test_mapping_value_is_kept(self):
        """Mappings are accepted as-is by scalar validator."""

        class ScalarInput(BaseInputScalarField):
            value: int

        parsed = ScalarInput.model_validate({"value": 8})

        assert parsed.value == 8

    def test_multiple_fields_scalar_raises_type_error(self):
        """Scalar input with multi-field model should fail."""

        class MultiInput(BaseInputScalarField):
            a: int
            b: int

        with pytest.raises(TypeError):
            MultiInput.model_validate(1)


class TestBaseInputFieldEnumModel:
    """Tests for BaseInputFieldEnumModel class."""

    def test_base_input_field_enum_model(self):
        """Test BaseInputFieldEnumModel stores key and input_model."""

        class TestInput(BaseInputField):
            value: float

        class TestFieldEnum(BaseInputFieldEnumModel):
            POWER = "power", TestInput

        assert TestFieldEnum.POWER.key == "power"
        assert TestFieldEnum.POWER.input_model == TestInput


class TestBaseField:
    """Tests for BaseField class."""

    def test_base_field_basic(self):
        """Test BaseField basic creation."""

        class TestField(BaseField):
            POWER = "power"

        assert str(TestField.POWER) == "power"

    def test_base_field_field_method(self):
        """Test BaseField.field method generates correct dict."""

        class TestField(BaseField):
            POWER = "power"

        result = TestField.POWER.field("Power Value")

        assert result["title"] == "Power Value"
        assert "json_schema_extra" in result
        assert result["json_schema_extra"]["input_field"] is None

    def test_base_field_field_with_input_field(self):
        """Test BaseField.field method with input_field."""

        class TestInput(BaseInputField):
            value: float

        class TestFieldEnum(BaseInputFieldEnumModel):
            POWER = "power", TestInput

        class TestField(BaseField):
            POWER = "power", TestFieldEnum.POWER

        result = TestField.POWER.field("Power Value")

        assert result["title"] == "Power Value"
        assert result["json_schema_extra"]["input_field"] == "power"

    def test_base_field_field_with_json_schema_extra(self):
        """Test BaseField.field method with custom json_schema_extra."""

        class TestField(BaseField):
            POWER = "power"

        result = TestField.POWER.field(
            "Power Value",
            unit="W",
        )

        assert result["title"] == "Power Value"
        assert result["json_schema_extra"]["unit"] == "W"


class TestSolaredge2MQTTBaseModel:
    """Tests for Solaredge2MQTTBaseModel class."""

    def test_auto_timestamp(self):
        """Test that timestamp is automatically set if not provided."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        model = TestModel(value=42)
        assert model.timestamp is not None
        assert model.timestamp.tzinfo is not None

    def test_manual_timestamp(self):
        """Test that provided timestamp is preserved."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        model = TestModel(value=42, timestamp=ts)
        assert model.timestamp == ts

    def test_model_dump_influxdb(self):
        """Test model_dump_influxdb flattens nested data."""

        class NestedModel(Solaredge2MQTTBaseModel):
            inner_value: int

        class TestModel(Solaredge2MQTTBaseModel):
            value: int
            nested: NestedModel

        model = TestModel(
            value=42,
            nested=NestedModel(inner_value=100),
        )
        result = model.model_dump_influxdb()

        assert "value" in result
        assert result["value"] == pytest.approx(42.0)
        assert "nested_inner_value" in result
        assert result["nested_inner_value"] == pytest.approx(100.0)
        assert "timestamp" not in result

    def test_flatten_dict_converts_int_to_float(self):
        """Test that _flatten_dict converts int to float."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        model = TestModel(value=42)
        result = model.model_dump_influxdb()

        assert isinstance(result["value"], float)

    def test_flatten_dict_handles_datetime(self):
        """Test that _flatten_dict converts datetime to isoformat."""

        class TestModel(Solaredge2MQTTBaseModel):
            event_time: datetime

        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        model = TestModel(event_time=ts)
        result = model.model_dump_influxdb()

        assert result["event_time"] == ts.isoformat()

    def test_default_homeassistant_device_info(self):
        """Test _default_homeassistant_device_info method.

        Note: Testing protected method directly is intentional for thorough
        coverage of internal implementation behavior.
        """

        class DeviceInfoModel(Solaredge2MQTTBaseModel):
            """Model for testing device info."""

            value: int

        model = DeviceInfoModel(value=42)
        # Access to protected member is intentional for testing
        info = model._default_homeassistant_device_info("Test Device")  # noqa: SLF001

        assert info["name"] == "SolarEdge2MQTT Test Device"
        assert info["manufacturer"] == "DerOetzi"
        assert info["model"] == "SolarEdge2MQTT"
        assert "sw_version" in info

    def test_parse_schema_basic(self):
        """Test parse_schema method with simple model."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        # This tests that the method runs without error
        result = TestModel.parse_schema()
        assert isinstance(result, list)

    def test_parse_schema_with_allof_and_anyof_paths(self):
        """parse_schema handles nested object trees via recursion helper."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        parser_calls: list[tuple[str, list[str]]] = []

        def parser(prop, name, path):
            parser_calls.append((name, path))
            return {"name": name, "path": path, "prop": prop.get("type")}

        properties = {
            "group": {
                "title": "Group",
                "properties": {
                    "leaf": {"title": "Leaf", "type": "number", "input_field": "test"}
                },
            },
            "all_of_group": {
                "title": "AllOf Group",
                "allOf": [
                    {
                        "properties": {
                            "leaf2": {
                                "title": "Leaf2",
                                "type": "integer",
                                "input_field": "test2",
                            }
                        }
                    }
                ],
            },
            "any_of_group": {
                "title": "AnyOf Group",
                "anyOf": [
                    {
                        "properties": {
                            "leaf3": {
                                "title": "Leaf3",
                                "type": "boolean",
                                "input_field": "test3",
                            }
                        }
                    }
                ],
            },
        }

        items = TestModel._walk_schema(properties, parser)  # noqa: SLF001

        assert len(items) == 3
        assert any(call[0].endswith("Leaf") for call in parser_calls)
        assert any(call[1] == ["group", "leaf"] for call in parser_calls)

    def test_property_parser_without_input_field_returns_none(self):
        """property_parser ignores schema fields without input_field metadata."""
        result = Solaredge2MQTTBaseModel.property_parser(
            {"type": "number"},
            "Value",
            ["value"],
        )

        assert result is None

    def test_property_parser_with_input_field(self):
        """property_parser returns payload when input_field metadata exists."""
        result = Solaredge2MQTTBaseModel.property_parser(
            {"type": "number", "input_field": "power"},
            "Power",
            ["inverter", "power"],
        )

        assert result == {
            "name": "Power",
            "path": ["inverter", "power"],
            "input_field": "power",
        }

    def test_flatten_dict_initializes_ignore_keys_when_none(self):
        """_flatten_dict initializes ignore_keys when argument is None."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        model = TestModel(value=1)
        flattened = model._flatten_dict({"value": 1}, ignore_keys=None)  # noqa: SLF001

        assert flattened["value"] == pytest.approx(1.0)

    def test_parse_schema_handles_non_mapping_replace_refs(self, monkeypatch):
        """parse_schema returns empty list when replace_refs result is non-mapping."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        monkeypatch.setattr(
            "solaredge2mqtt.core.models.jsonref.replace_refs",
            lambda *args, **kwargs: ["not", "a", "mapping"],
        )

        assert TestModel.parse_schema() == []

    def test_parse_schema_handles_non_mapping_properties(self, monkeypatch):
        """parse_schema ignores non-mapping properties payloads."""

        class TestModel(Solaredge2MQTTBaseModel):
            value: int

        monkeypatch.setattr(
            "solaredge2mqtt.core.models.jsonref.replace_refs",
            lambda *args, **kwargs: {"properties": ["invalid"]},
        )

        assert TestModel.parse_schema() == []
