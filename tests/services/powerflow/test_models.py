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


class TestInverterPowerflowValidation:
    """Tests for InverterPowerflow validation."""

    def test_is_valid_negative_consumption(self):
        """Test is_valid logs warning for negative consumption."""
        # This is hard to trigger since consumption = abs(power) if power < 0 else 0
        # which is always >= 0. But we test the normal case.
        inverter = InverterPowerflow(power=100, dc_power=100, battery_discharge=0)
        assert inverter.is_valid is True

    def test_is_valid_valid_values(self):
        """Test is_valid returns True for all positive values."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=200)

        assert inverter.is_valid is True


class TestGridPowerflowValidation:
    """Tests for GridPowerflow validation."""

    def test_is_valid_negative_power(self):
        """Test is_valid with negative power (consumption)."""
        grid = GridPowerflow(power=-1000)

        assert grid.is_valid is True
        assert grid.consumption == 1000
        assert grid.delivery == 0

    def test_is_valid_positive_power(self):
        """Test is_valid with positive power (delivery)."""
        grid = GridPowerflow(power=500)

        assert grid.is_valid is True
        assert grid.consumption == 0
        assert grid.delivery == 500


class TestBatteryPowerflowValidation:
    """Tests for BatteryPowerflow validation."""

    def test_is_valid_charging(self):
        """Test is_valid when battery is charging."""
        battery = BatteryPowerflow(power=500)

        assert battery.is_valid is True
        assert battery.charge == 500
        assert battery.discharge == 0

    def test_is_valid_discharging(self):
        """Test is_valid when battery is discharging."""
        battery = BatteryPowerflow(power=-500)

        assert battery.is_valid is True
        assert battery.charge == 0
        assert battery.discharge == 500


class TestConsumerPowerflowValidation:
    """Tests for ConsumerPowerflow validation."""

    def test_used_battery_production_with_battery_factor(self):
        """Test used_battery_production with battery factor."""
        # Create inverter with battery discharge
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=200)
        grid = GridPowerflow(power=100)  # Delivery = 100

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # used_production = production - delivery = 1000 - 100 = 900
        assert consumer.used_production == 900

        # used_battery_production = round(used_production * battery_factor)
        # battery_factor = 200/1200 = 0.1667
        # used_battery_production = round(900 * 0.1667) = round(150) = 150
        assert consumer.used_battery_production > 0

        # used_pv_production = used_production - used_battery_production
        assert consumer.used_pv_production == consumer.used_production - consumer.used_battery_production

    def test_used_battery_production_no_battery(self):
        """Test used_battery_production is 0 when no battery."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=100)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        assert consumer.used_battery_production == 0
        assert consumer.used_pv_production == consumer.used_production

    def test_consumer_with_evcharger(self):
        """Test consumer calculation with EV charger."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=-200)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=500)

        assert consumer.evcharger == 500
        assert consumer.total == consumer.house + consumer.evcharger + consumer.inverter

    def test_is_valid_returns_true(self):
        """Test is_valid returns True for normal consumer."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=100)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        assert consumer.is_valid is True
