"""Tests for services models module."""

from datetime import datetime

from solaredge2mqtt.services.models import Component, ComponentValueGroup


class TestComponentValueGroup:
    """Tests for ComponentValueGroup class."""

    def test_scale_value_positive_scale(self):
        """Test scale_value with positive scale."""
        data = {"power": 100, "power_scale": 2}
        result = ComponentValueGroup.scale_value(data, "power")

        # 100 * 10^2 = 10000
        assert result == 10000.0

    def test_scale_value_negative_scale(self):
        """Test scale_value with negative scale."""
        data = {"power": 12345, "power_scale": -2}
        result = ComponentValueGroup.scale_value(data, "power")

        # 12345 * 10^-2 = 123.45
        assert result == 123.45

    def test_scale_value_zero_scale(self):
        """Test scale_value with zero scale."""
        data = {"power": 500, "power_scale": 0}
        result = ComponentValueGroup.scale_value(data, "power")

        # 500 * 10^0 = 500
        assert result == 500.0

    def test_scale_value_custom_scale_key(self):
        """Test scale_value with custom scale key."""
        data = {"voltage": 2300, "custom_scale": -1}
        result = ComponentValueGroup.scale_value(data, "voltage", "custom_scale")

        # 2300 * 10^-1 = 230
        assert result == 230.0

    def test_scale_value_custom_digits(self):
        """Test scale_value with custom digit precision."""
        data = {"power": 333, "power_scale": -2}
        result = ComponentValueGroup.scale_value(data, "power", digits=4)

        # 333 * 10^-2 = 3.33 rounded to 4 digits
        assert result == 3.33

    def test_scale_value_rounding(self):
        """Test scale_value rounds correctly."""
        data = {"power": 12345, "power_scale": -4}
        result = ComponentValueGroup.scale_value(data, "power", digits=2)

        # 12345 * 10^-4 = 1.2345 rounded to 2 digits = 1.23
        assert result == 1.23


class TestComponent:
    """Tests for Component class."""

    def test_component_default_values(self):
        """Test Component class defaults."""
        assert Component.COMPONENT == "unknown"
        assert Component.SOURCE is None

    def test_component_influxdb_tags(self):
        """Test Component influxdb_tags property."""

        class TestComponent(Component):
            COMPONENT = "test_component"
            SOURCE = "test_source"

        component = TestComponent()
        tags = component.influxdb_tags

        assert tags["component"] == "test_component"
        assert tags["source"] == "test_source"

    def test_component_mqtt_topic_with_source(self):
        """Test Component mqtt_topic with source."""

        class TestComponent(Component):
            COMPONENT = "inverter"
            SOURCE = "modbus"

        component = TestComponent()
        topic = component.mqtt_topic()

        assert topic == "modbus/inverter"

    def test_component_mqtt_topic_without_source(self):
        """Test Component mqtt_topic without source."""

        class TestComponent(Component):
            COMPONENT = "powerflow"
            SOURCE = None

        component = TestComponent()
        topic = component.mqtt_topic()

        assert topic == "powerflow"

    def test_component_str_with_source(self):
        """Test Component string representation with source."""

        class TestComponent(Component):
            COMPONENT = "meter"
            SOURCE = "modbus"

        component = TestComponent()

        assert str(component) == "modbus: meter"

    def test_component_str_without_source(self):
        """Test Component string representation without source."""

        class TestComponent(Component):
            COMPONENT = "powerflow"
            SOURCE = None

        component = TestComponent()

        assert str(component) == "powerflow"

    def test_component_has_timestamp(self):
        """Test Component has timestamp from base model."""

        class TestComponent(Component):
            COMPONENT = "test"

        component = TestComponent()

        assert component.timestamp is not None
        assert isinstance(component.timestamp, datetime)
