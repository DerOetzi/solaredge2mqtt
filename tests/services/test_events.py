"""Tests for services events module."""

from unittest.mock import MagicMock


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

        component = MagicMock(spec=Component)
        event = ComponentEvent(component)

        assert event.component is component

    def test_component_event_str(self):
        """Test ComponentEvent string representation."""

        component = MagicMock(spec=Component)
        component.__str__.return_value = "modbus: inverter"
        event = ComponentEvent(component)

        assert str(event) == "modbus: inverter"


class TestComponentsEvent:
    """Tests for ComponentsEvent class."""

    def test_components_event_is_base_event(self):
        """Test ComponentsEvent inherits from BaseEvent."""
        assert issubclass(ComponentsEvent, BaseEvent)

    def test_components_event_stores_components(self):
        """Test ComponentsEvent stores components dict."""

        component1 = MagicMock(spec=Component)
        component2 = MagicMock(spec=Component)
        components = {"c1": component1, "c2": component2}

        event = ComponentsEvent(components)

        assert event.components == components
        assert event.components["c1"] is component1
        assert event.components["c2"] is component2

    def test_components_event_str(self):
        """Test ComponentsEvent string representation."""

        components = {"key": MagicMock(spec=Component)}
        event = ComponentsEvent(components)

        assert str(event) == str(components)
