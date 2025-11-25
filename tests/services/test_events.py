"""Tests for services events module."""


from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.events import ComponentEvent, ComponentsEvent
from solaredge2mqtt.services.models import Component


class TestComponentEvent:
    """Tests for ComponentEvent class."""

    def test_component_event_is_base_event(self):
        """Test ComponentEvent inherits from BaseEvent."""
        assert issubclass(ComponentEvent, BaseEvent)

    def test_component_event_stores_component(self):
        """Test ComponentEvent stores component."""

        class TestComponent(Component):
            COMPONENT = "test"

        component = TestComponent()
        event = ComponentEvent(component)

        assert event.component is component

    def test_component_event_str(self):
        """Test ComponentEvent string representation."""

        class TestComponent(Component):
            COMPONENT = "inverter"
            SOURCE = "modbus"

        component = TestComponent()
        event = ComponentEvent(component)

        assert str(event) == "modbus: inverter"


class TestComponentsEvent:
    """Tests for ComponentsEvent class."""

    def test_components_event_is_base_event(self):
        """Test ComponentsEvent inherits from BaseEvent."""
        assert issubclass(ComponentsEvent, BaseEvent)

    def test_components_event_stores_components(self):
        """Test ComponentsEvent stores components dict."""

        class TestComponent(Component):
            COMPONENT = "test"

        component1 = TestComponent()
        component2 = TestComponent()
        components = {"c1": component1, "c2": component2}

        event = ComponentsEvent(components)

        assert event.components == components
        assert event.components["c1"] is component1
        assert event.components["c2"] is component2

    def test_components_event_str(self):
        """Test ComponentsEvent string representation."""

        class TestComponent(Component):
            COMPONENT = "test"

        components = {"key": TestComponent()}
        event = ComponentsEvent(components)

        assert str(event) == str(components)
