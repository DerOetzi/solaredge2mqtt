"""Tests for energy events module."""

from datetime import datetime, timezone

import pytest

from solaredge2mqtt.services.energy.events import EnergyReadEvent
from solaredge2mqtt.services.energy.models import HistoricEnergy, HistoricPeriod
from solaredge2mqtt.services.events import ComponentEvent


def make_historic_energy_data() -> dict:
    """Create historic energy data for testing."""
    return {
        "_start": datetime(2024, 6, 15, 0, 0, tzinfo=timezone.utc),
        "_stop": datetime(2024, 6, 15, 23, 59, tzinfo=timezone.utc),
        "pv_production": 100.0,
        "inverter_production": 100.0,
        "inverter_consumption": 10.0,
        "inverter_dc_power": 5000.0,
        "inverter_pv_production": 80.0,
        "inverter_battery_production": 20.0,
        "grid_delivery": 30.0,
        "grid_consumption": 10.0,
        "battery_charge": 15.0,
        "battery_discharge": 20.0,
        "consumer_house": 50.0,
        "consumer_evcharger": 5.0,
        "consumer_inverter": 5.0,
        "consumer_total": 60.0,
        "consumer_used_production": 55.0,
        "consumer_used_pv_production": 40.0,
        "consumer_used_battery_production": 15.0,
    }


class TestEnergyReadEvent:
    """Tests for EnergyReadEvent class."""

    def test_event_is_component_event(self):
        """Test EnergyReadEvent inherits from ComponentEvent."""
        assert issubclass(EnergyReadEvent, ComponentEvent)

    def test_event_component_property(self):
        """Test component property returns energy component."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        event = EnergyReadEvent(energy)

        assert event.component is energy
        assert event.component.info.period == HistoricPeriod.TODAY
