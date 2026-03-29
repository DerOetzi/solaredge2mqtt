"""Tests for services models module."""

import pytest

from solaredge2mqtt.services.models import Component, HTTPResponse, TComponent


class ConcreteComponent(Component):
    """Concrete Component implementation for testing."""

    COMPONENT = "test_component"
    SOURCE = "test_source"

    def homeassistant_device_info(self) -> dict[str, str]:
        """Return Home Assistant device info."""
        return {
            "name": "Test Component",
            "manufacturer": "Test",
        }


class ConcreteComponentNoSource(Component):
    """Concrete Component implementation without source for testing."""

    COMPONENT = "no_source_component"
    SOURCE = None

    def homeassistant_device_info(self) -> dict[str, str]:
        """Return Home Assistant device info."""
        return {"name": "No Source Component"}


class TestComponent:
    """Tests for Component base class."""

    def test_influxdb_tags_with_source(self):
        """Test influxdb_tags property with source."""
        component = ConcreteComponent()

        tags = component.influxdb_tags

        assert tags["component"] == "test_component"
        assert tags["source"] == "test_source"

    def test_influxdb_tags_without_source(self):
        """Test influxdb_tags property without source."""
        component = ConcreteComponentNoSource()

        tags = component.influxdb_tags

        assert tags["component"] == "no_source_component"
        assert tags["source"] == ""

    def test_mqtt_topic_with_source(self):
        """Test mqtt_topic method with source."""
        component = ConcreteComponent()

        topic = component.mqtt_topic()

        assert topic == "test_source/test_component"

    def test_mqtt_topic_without_source(self):
        """Test mqtt_topic method without source."""
        component = ConcreteComponentNoSource()

        topic = component.mqtt_topic()

        assert topic == "no_source_component"

    def test_str_with_source(self):
        """Test __str__ method with source."""
        component = ConcreteComponent()

        name = str(component)

        assert name == "test_source: test_component"

    def test_str_without_source(self):
        """Test __str__ method without source."""
        component = ConcreteComponentNoSource()

        name = str(component)

        assert name == "no_source_component"

    def test_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        component = ConcreteComponent()

        info = component.homeassistant_device_info()

        assert isinstance(info, dict)
        assert info["name"] == "Test Component"
        assert info["manufacturer"] == "Test"

    def test_component_is_solaredge2mqtt_base_model(self):
        """Test Component inherits from Solaredge2MQTTBaseModel."""
        from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel

        assert issubclass(Component, Solaredge2MQTTBaseModel)

    def test_abstract_homeassistant_device_info(self):
        """Test that homeassistant_device_info is abstract."""
        # Component class should not be instantiable directly
        # because of abstract method
        with pytest.raises(TypeError):
            Component()  # type: ignore[abstract]

    def test_base_abstract_method_body_is_callable(self):
        """Call abstract method implementation directly for branch coverage."""
        component = ConcreteComponent()

        assert Component.homeassistant_device_info(component) is None


class TestHTTPResponse:
    """Tests for HTTPResponse type alias."""

    def test_http_response_dict(self):
        """Test HTTPResponse with dict."""
        response: HTTPResponse = {"key": "value"}

        assert isinstance(response, dict)
        assert response["key"] == "value"

    def test_http_response_string(self):
        """Test HTTPResponse with string."""
        response: HTTPResponse = "response_string"

        assert isinstance(response, str)
        assert response == "response_string"


class TestTComponent:
    """Tests for TComponent TypeVar."""

    def test_tcomponent_bound_to_component(self):
        """Test TComponent is bound to Component."""

        # Create a function using TComponent
        def process_component(comp: TComponent) -> TComponent:
            return comp

        concrete = ConcreteComponent()
        result = process_component(concrete)

        assert result == concrete
        assert isinstance(result, Component)
