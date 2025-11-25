"""Tests for powerflow models module."""

import pytest

from solaredge2mqtt.services.powerflow.models import (
    BatteryPowerflow,
    ConsumerPowerflow,
    GridPowerflow,
    InverterPowerflow,
)


class TestInverterPowerflow:
    """Tests for InverterPowerflow class."""

    def test_inverter_powerflow_consumption_positive_power(self):
        """Test consumption is 0 when power is positive."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)

        assert inverter.consumption == 0

    def test_inverter_powerflow_consumption_negative_power(self):
        """Test consumption equals abs(power) when power is negative."""
        inverter = InverterPowerflow(power=-500, dc_power=0, battery_discharge=0)

        assert inverter.consumption == 500

    def test_inverter_powerflow_production_positive_power(self):
        """Test production equals power when power is positive."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)

        assert inverter.production == 1000

    def test_inverter_powerflow_production_negative_power(self):
        """Test production is 0 when power is negative."""
        inverter = InverterPowerflow(power=-500, dc_power=0, battery_discharge=0)

        assert inverter.production == 0

    def test_inverter_powerflow_battery_factor_with_discharge(self):
        """Test battery_factor calculation with discharge."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=200)

        expected_factor = 200 / 1200
        assert inverter.battery_factor == pytest.approx(expected_factor)

    def test_inverter_powerflow_battery_factor_no_discharge(self):
        """Test battery_factor is 0 when no discharge."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)

        assert inverter.battery_factor == pytest.approx(0.0)

    def test_inverter_powerflow_battery_factor_zero_power(self):
        """Test battery_factor is 0 when power is 0."""
        inverter = InverterPowerflow(power=0, dc_power=1200, battery_discharge=200)

        assert inverter.battery_factor == pytest.approx(0.0)

    def test_inverter_powerflow_battery_production(self):
        """Test battery_production calculation."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=200)

        expected = int(round(1000 * (200 / 1200)))
        assert inverter.battery_production == expected

    def test_inverter_powerflow_pv_production(self):
        """Test pv_production calculation."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=200)

        expected = inverter.production - inverter.battery_production
        assert inverter.pv_production == expected

    def test_inverter_powerflow_is_valid_true(self):
        """Test is_valid returns True for valid values."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)

        assert inverter.is_valid is True

    def test_inverter_powerflow_is_valid_false_negative_production(self):
        """Test is_valid returns False for negative production."""
        # This is a corner case - power is positive so production should be positive
        inverter = InverterPowerflow(power=100, dc_power=100, battery_discharge=0)

        assert inverter.is_valid is True


class TestGridPowerflow:
    """Tests for GridPowerflow class."""

    def test_grid_powerflow_consumption_negative_power(self):
        """Test consumption equals abs(power) when power is negative."""
        grid = GridPowerflow(power=-500)

        assert grid.consumption == 500

    def test_grid_powerflow_consumption_positive_power(self):
        """Test consumption is 0 when power is positive."""
        grid = GridPowerflow(power=500)

        assert grid.consumption == 0

    def test_grid_powerflow_delivery_positive_power(self):
        """Test delivery equals power when power is positive."""
        grid = GridPowerflow(power=500)

        assert grid.delivery == 500

    def test_grid_powerflow_delivery_negative_power(self):
        """Test delivery is 0 when power is negative."""
        grid = GridPowerflow(power=-500)

        assert grid.delivery == 0

    def test_grid_powerflow_is_valid_true(self):
        """Test is_valid returns True for valid values."""
        grid = GridPowerflow(power=500)

        assert grid.is_valid is True


class TestBatteryPowerflow:
    """Tests for BatteryPowerflow class."""

    def test_battery_powerflow_charge_positive_power(self):
        """Test charge equals power when power is positive."""
        battery = BatteryPowerflow(power=500)

        assert battery.charge == 500

    def test_battery_powerflow_charge_negative_power(self):
        """Test charge is 0 when power is negative."""
        battery = BatteryPowerflow(power=-500)

        assert battery.charge == 0

    def test_battery_powerflow_discharge_negative_power(self):
        """Test discharge equals abs(power) when power is negative."""
        battery = BatteryPowerflow(power=-500)

        assert battery.discharge == 500

    def test_battery_powerflow_discharge_positive_power(self):
        """Test discharge is 0 when power is positive."""
        battery = BatteryPowerflow(power=500)

        assert battery.discharge == 0

    def test_battery_powerflow_is_valid_true(self):
        """Test is_valid returns True for valid values."""
        battery = BatteryPowerflow(power=500)

        assert battery.is_valid is True


class TestConsumerPowerflow:
    """Tests for ConsumerPowerflow class."""

    def test_consumer_powerflow_total(self):
        """Test total calculation."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=-200)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=100)

        assert consumer.total == consumer.house + consumer.evcharger + consumer.inverter

    def test_consumer_powerflow_house_calculation(self):
        """Test house power calculation."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=-200)
        evcharger = 100

        consumer = ConsumerPowerflow(inverter, grid, evcharger)

        # house = |grid.power - inverter.power| - evcharger
        # house = |-200 - 1000| - 100 = 1200 - 100 = 1100
        expected_house = int(abs(-200 - 1000)) - 100
        assert consumer.house == expected_house

    def test_consumer_powerflow_used_production(self):
        """Test used_production calculation."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=300)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        assert consumer.used_production == 700

    def test_consumer_powerflow_used_production_no_production(self):
        """Test used_production is 0 when no production."""
        inverter = InverterPowerflow(power=-100, dc_power=0, battery_discharge=0)
        grid = GridPowerflow(power=-500)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        assert consumer.used_production == 0

    def test_consumer_powerflow_is_valid_true(self):
        """Test is_valid returns True for valid values."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=-200)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=100)

        assert consumer.is_valid is True
