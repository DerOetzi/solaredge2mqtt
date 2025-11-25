"""Tests for services models module."""

from datetime import datetime

import pytest

from solaredge2mqtt.services.models import Component, ComponentValueGroup


class TestComponentValueGroup:
    """Tests for ComponentValueGroup class."""

    def test_scale_value_positive_scale(self):
        """Test scale_value with positive scale."""
        data = {"power": 100, "power_scale": 2}
        result = ComponentValueGroup.scale_value(data, "power")

        assert result == pytest.approx(10000.0)

    def test_scale_value_negative_scale(self):
        """Test scale_value with negative scale."""
        data = {"power": 12345, "power_scale": -2}
        result = ComponentValueGroup.scale_value(data, "power")

        assert result == pytest.approx(123.45)

    def test_scale_value_zero_scale(self):
        """Test scale_value with zero scale."""
        data = {"power": 500, "power_scale": 0}
        result = ComponentValueGroup.scale_value(data, "power")

        assert result == pytest.approx(500.0)

    def test_scale_value_custom_scale_key(self):
        """Test scale_value with custom scale key."""
        data = {"voltage": 2300, "custom_scale": -1}
        result = ComponentValueGroup.scale_value(data, "voltage", "custom_scale")

        assert result == pytest.approx(230.0)

    def test_scale_value_custom_digits(self):
        """Test scale_value with custom digit precision."""
        data = {"power": 333, "power_scale": -2}
        result = ComponentValueGroup.scale_value(data, "power", digits=4)

        assert result == pytest.approx(3.33)

    def test_scale_value_rounding(self):
        """Test scale_value rounds correctly."""
        data = {"power": 12345, "power_scale": -4}
        result = ComponentValueGroup.scale_value(data, "power", digits=2)

        assert result == pytest.approx(1.23)


class TestComponentBase:
    """Tests for Component class."""

    def test_component_default_values(self):
        """Test Component class defaults."""
        assert Component.COMPONENT == "unknown"
        assert Component.SOURCE is None

    def test_component_influxdb_tags(self):
        """Test Component influxdb_tags property."""

        class SampleComponent(Component):
            """Sample component for testing."""

            COMPONENT = "test_component"
            SOURCE = "test_source"

        component = SampleComponent()
        tags = component.influxdb_tags

        assert tags["component"] == "test_component"
        assert tags["source"] == "test_source"

    def test_component_mqtt_topic_with_source(self):
        """Test Component mqtt_topic with source."""

        class InverterComponent(Component):
            """Inverter component for testing."""

            COMPONENT = "inverter"
            SOURCE = "modbus"

        component = InverterComponent()
        topic = component.mqtt_topic()

        assert topic == "modbus/inverter"

    def test_component_mqtt_topic_without_source(self):
        """Test Component mqtt_topic without source."""

        class PowerflowComponent(Component):
            """Powerflow component for testing."""

            COMPONENT = "powerflow"
            SOURCE = None

        component = PowerflowComponent()
        topic = component.mqtt_topic()

        assert topic == "powerflow"

    def test_component_str_with_source(self):
        """Test Component string representation with source."""

        class MeterComponent(Component):
            """Meter component for testing."""

            COMPONENT = "meter"
            SOURCE = "modbus"

        component = MeterComponent()

        assert str(component) == "modbus: meter"

    def test_component_str_without_source(self):
        """Test Component string representation without source."""

        class PowerflowComponent(Component):
            """Powerflow component for testing."""

            COMPONENT = "powerflow"
            SOURCE = None

        component = PowerflowComponent()

        assert str(component) == "powerflow"

    def test_component_has_timestamp(self):
        """Test Component has timestamp from base model."""

        class TimestampComponent(Component):
            """Component for testing timestamps."""

            COMPONENT = "test"

        component = TimestampComponent()

        assert component.timestamp is not None
        assert isinstance(component.timestamp, datetime)
