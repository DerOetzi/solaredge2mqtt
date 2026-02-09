"""Tests for powerflow models - additional tests for better coverage."""

from solaredge2mqtt.services.modbus.models.base import (
    ModbusUnitInfo,
    ModbusUnitRole,
)
from solaredge2mqtt.services.powerflow.models import (
    BatteryPowerflow,
    ConsumerPowerflow,
    GridPowerflow,
    InverterPowerflow,
    Powerflow,
)


class TestPowerflow:
    """Additional tests for Powerflow class."""

    def test_powerflow_creation_basic(self):
        """Test basic Powerflow creation."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.pv_production == 1200
        assert powerflow.inverter == inverter
        assert powerflow.grid == grid
        assert powerflow.battery == battery
        assert powerflow.consumer == consumer

    def test_powerflow_with_unit_info(self):
        """Test Powerflow with unit info."""
        unit_info = ModbusUnitInfo(
            key="leader",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            unit=unit_info,
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.has_unit is True
        assert powerflow.unit.key == "leader"

    def test_powerflow_has_unit_false(self):
        """Test has_unit returns False when no unit."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.has_unit is False

    def test_powerflow_mqtt_topic_without_unit(self):
        """Test mqtt_topic without unit."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.mqtt_topic() == "powerflow"

    def test_powerflow_mqtt_topic_with_unit(self):
        """Test mqtt_topic with unit."""
        unit_info = ModbusUnitInfo(
            key="leader",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            unit=unit_info,
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.mqtt_topic() == "powerflow/leader"

    def test_powerflow_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        ha_info = powerflow.homeassistant_device_info()

        assert "Powerflow" in ha_info["name"]

    def test_powerflow_homeassistant_device_info_with_unit(self):
        """Test homeassistant_device_info with unit."""
        unit_info = ModbusUnitInfo(
            key="Leader",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            unit=unit_info,
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        ha_info = powerflow.homeassistant_device_info()

        assert "Powerflow" in ha_info["name"]
        assert "Leader" in ha_info["name"]

    def test_powerflow_is_valid_true(self):
        """Test is_valid returns True for valid powerflow."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=0)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1000,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.is_valid(external_production=False) is True

    def test_powerflow_is_valid_negative_pv_production(self):
        """Test is_valid returns False for negative PV production."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=-100,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        assert powerflow.is_valid(external_production=False) is False

    def test_powerflow_prepare_point(self):
        """Test prepare_point method."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        point = powerflow.prepare_point()

        assert point._name == "powerflow_raw"

    def test_powerflow_prepare_point_with_unit(self):
        """Test prepare_point with unit tag."""
        unit_info = ModbusUnitInfo(
            key="leader",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            unit=unit_info,
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        point = powerflow.prepare_point()

        # Check tag is set (accessing internal dict)
        assert "unit" in dict(point._tags)

    def test_powerflow_cumulated(self):
        """Test cumulated_powerflow static method."""
        # Create two powerflows
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid1 = GridPowerflow(power=-200)
        battery1 = BatteryPowerflow(power=0)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            pv_production=1200,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        inverter2 = InverterPowerflow(
            power=500, dc_power=600, battery_discharge=0
        )
        grid2 = GridPowerflow(power=-100)
        battery2 = BatteryPowerflow(power=0)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            pv_production=600,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        assert cumulated.pv_production == 1800  # 1200 + 600
        assert cumulated.inverter.power == 1500  # 1000 + 500
        assert cumulated.unit.role == ModbusUnitRole.CUMULATED

    def test_powerflow_is_not_valid_with_last_first_call(self):
        """Test is_not_valid_with_last on first call."""
        # Reset class variable
        Powerflow.last_powerflow = None

        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        # First call should return False (no last_powerflow)
        result = Powerflow.is_not_valid_with_last(powerflow)

        assert result is False

    def test_powerflow_is_not_valid_with_last_sudden_increase(self):
        """Test is_not_valid_with_last detects sudden increase."""
        # Set up last_powerflow with 0 production
        inverter_last = InverterPowerflow(
            power=0, dc_power=0, battery_discharge=0
        )
        grid_last = GridPowerflow(power=0)
        battery_last = BatteryPowerflow(power=0)
        consumer_last = ConsumerPowerflow(
            inverter_last, grid_last, evcharger=0
        )

        last_powerflow = Powerflow(
            pv_production=0,
            inverter=inverter_last,
            grid=grid_last,
            battery=battery_last,
            consumer=consumer_last,
        )
        Powerflow.last_powerflow = last_powerflow

        # Current powerflow with sudden increase > 100
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=200,  # Sudden increase from 0 to 200 (>100)
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        result = Powerflow.is_not_valid_with_last(powerflow)

        # Should detect invalid jump
        assert result is True


class TestInverterPowerflowValidation:
    """Additional validation tests for InverterPowerflow."""

    def test_inverter_battery_production_capped(self):
        """Test battery_production is capped at production."""
        # Scenario where battery_factor * production > production
        # This shouldn't happen in real data but tests the min() cap
        inverter = InverterPowerflow(
            power=100, dc_power=50, battery_discharge=100
        )

        # battery_factor = 100 / 50 = 2.0
        # battery_production = round(100 * 2.0) = 200 -> capped at 100
        assert inverter.battery_production <= inverter.production


class TestConsumerPowerflowValidation:
    """Additional validation tests for ConsumerPowerflow."""

    def test_consumer_used_battery_production_capped(self):
        """Test used_battery_production is capped at used_production."""
        inverter = InverterPowerflow(
            power=100, dc_power=50, battery_discharge=100
        )
        grid = GridPowerflow(power=0)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # used_battery_production should not exceed used_production
        assert consumer.used_battery_production <= consumer.used_production

    def test_consumer_used_production_exceeds_grid_delivery(self):
        """Test used_production when production exceeds grid delivery."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=300)  # Delivering 300 to grid

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # used_production = production - grid.delivery = 1000 - 300 = 700
        assert consumer.used_production == 700

    def test_consumer_used_production_when_production_less_than_delivery(self):
        """Test used_production is 0 when production <= grid delivery."""
        inverter = InverterPowerflow(
            power=200, dc_power=250, battery_discharge=0
        )
        grid = GridPowerflow(power=300)  # Delivering more than production

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # production (200) < grid.delivery (300), so used_production = 0
        assert consumer.used_production == 0

    def test_consumer_battery_charging_from_grid_no_double_count(self):
        """Test that battery charging from grid is not double-counted.

        When battery is charging from grid, the inverter consumes power.
        Most of that power goes to the battery, but we should still account
        for the difference (conversion losses).

        Scenario (perfect efficiency):
        - Battery charging: 500W (DC side)
        - Inverter consuming: 500W (AC side)
        - Grid importing: 600W (grid.power = -600)
        - House consumption: 100W
        - Inverter losses: 0W (perfect efficiency)
        """
        # Battery charging from grid: inverter is consuming 500W
        inverter = InverterPowerflow(
            power=-500, dc_power=0, battery_discharge=0
        )
        # Grid is importing 600W (negative = consuming from grid)
        grid = GridPowerflow(power=-600)
        # Battery is charging at 500W (same as inverter consumption)
        battery = BatteryPowerflow(power=500)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # Expected: house = |grid - inverter| = |-600 - (-500)| = 100
        assert consumer.house == 100

        # With perfect efficiency, inverter consumption after accounting
        # for battery charging should be 0
        assert consumer.inverter == 0, (
            f"Inverter consumption should be 0 with perfect efficiency "
            f"(got {consumer.inverter}W)."
        )

        # Total consumer = house + inverter + evcharger = 100 + 0 + 0
        assert consumer.total == 100

    def test_consumer_battery_charging_with_losses(self):
        """Test battery charging with conversion losses.

        When battery charges from grid, there are typically conversion
        losses (AC to DC). The inverter consumption is higher than the
        battery charge.

        Scenario (with losses):
        - Inverter consuming: 550W (AC side)
        - Battery charging: 520W (DC side)
        - Losses: 30W (550 - 520)
        - Grid importing: 650W
        - House consumption: 100W
        """
        # Inverter consuming 550W from AC side
        inverter = InverterPowerflow(
            power=-550, dc_power=0, battery_discharge=0
        )
        # Grid importing 650W
        grid = GridPowerflow(power=-650)
        # Battery charging at 520W (30W losses)
        battery = BatteryPowerflow(power=520)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # house = |grid - inverter| = |-650 - (-550)| = 100
        assert consumer.house == 100

        # Inverter consumption should be the losses: 550 - 520 = 30W
        assert consumer.inverter == 30, (
            f"Inverter consumption should account for losses "
            f"(550W - 520W = 30W), got {consumer.inverter}W"
        )

        # Total consumer = house + inverter + evcharger
        # = 100 + 30 + 0 = 130W
        assert consumer.total == 130

    def test_consumer_battery_charging_mixed_pv_and_grid(self):
        """Test battery charging from both PV production and grid.

        Scenario: Partly cloudy day - mixed PV and grid charging
        - PV Production: 2000W
        - Battery charging: 3000W
        - Grid importing: 2030W (supplements PV)
        - Inverter consuming: 1530W (from grid, AC side)
        """
        inverter = InverterPowerflow(
            power=-1530, dc_power=2000, battery_discharge=0
        )
        grid = GridPowerflow(power=-2030)
        battery = BatteryPowerflow(power=3000)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # house = |grid - inverter| = |-2030 - (-1530)| = 500
        assert consumer.house == 500

        # consumer.inverter = max(0, 1530 - 3000) = 0
        assert consumer.inverter == 0

        # Total = house + inverter = 500 + 0 = 500W
        assert consumer.total == 500

    def test_consumer_battery_charging_pv_only(self):
        """Test battery charging entirely from PV production.

        Scenario: PV-only charging with grid export
        - PV Production: 6000W
        - Battery charging: 3500W
        - Grid export: 500W (excess PV)
        - No grid import: 0W

        Note: consumer.house (5500W) represents the calculated power flow
        balance, which includes battery charging (3500W) in the formula.
        """
        inverter = InverterPowerflow(
            power=6000, dc_power=6000, battery_discharge=0
        )
        grid = GridPowerflow(power=500)
        battery = BatteryPowerflow(power=3500)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # With positive inverter power, inverter.consumption = 0
        assert consumer.inverter == 0

        # house = |grid - inverter| = |500 - 6000| = 5500
        assert consumer.house == 5500

        # Total = house + inverter = 5500 + 0 = 5500W
        assert consumer.total == 5500

        # Verify no grid import
        assert grid.consumption == 0
        assert grid.delivery == 500

    def test_consumer_battery_charging_pv_exceeds_max_rate(self):
        """Test PV production exceeding battery max charge rate.

        Scenario: High PV production, battery at max charge limit
        - PV Production: 10000W
        - Battery charging: 5000W (hardware max limit)
        - Grid export: 3500W (excess that can't be stored)

        Note: consumer.house (6500W) represents the calculated power flow
        balance, which includes battery charging (5000W) in the formula.
        """
        inverter = InverterPowerflow(
            power=10000, dc_power=10000, battery_discharge=0
        )
        grid = GridPowerflow(power=3500)
        battery = BatteryPowerflow(power=5000)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # With positive inverter power, inverter.consumption = 0
        assert consumer.inverter == 0

        # house = |grid - inverter| = |3500 - 10000| = 6500
        assert consumer.house == 6500

        # Total = 6500 + 0 = 6500W
        assert consumer.total == 6500

        # Verify grid export and battery at max
        assert grid.delivery == 3500
        assert grid.consumption == 0
        assert battery.charge == 5000

    def test_consumer_battery_charging_minimal_grid_contribution(self):
        """Test battery charging with minimal grid contribution.

        Scenario: Mostly PV with tiny grid supplement
        - PV Production: 4900W
        - Battery charging: 3000W
        - Grid import: 100W (small supplement)

        Note: consumer.house (0W) results from the power flow calculation
        where grid and inverter values cancel out in the formula.
        """
        inverter = InverterPowerflow(
            power=-100, dc_power=4900, battery_discharge=0
        )
        grid = GridPowerflow(power=-100)
        battery = BatteryPowerflow(power=3000)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # house = |grid - inverter| = |-100 - (-100)| = 0
        assert consumer.house == 0

        # consumer.inverter = max(0, 100 - 3000) = 0
        assert consumer.inverter == 0

        # Total = 0 + 0 = 0
        assert consumer.total == 0

    def test_consumer_battery_charging_exact_balance(self):
        """Test battery charging with exact PV/consumption balance.

        Scenario: PV exactly matches battery needs
        - PV Production: 5500W
        - Battery charging: 3500W
        - Grid import/export: 0W (perfect balance)

        Note: consumer.house (5500W) represents the calculated power flow
        balance, which includes battery charging (3500W) in the formula.
        """
        inverter = InverterPowerflow(
            power=5500, dc_power=5500, battery_discharge=0
        )
        grid = GridPowerflow(power=0)
        battery = BatteryPowerflow(power=3500)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # consumer.inverter = max(0, 0 - 3500) = 0
        assert consumer.inverter == 0

        # house = |0 - 5500| = 5500
        assert consumer.house == 5500

        # Total = 5500 + 0 = 5500
        assert consumer.total == 5500

        # Verify no grid interaction
        assert grid.consumption == 0
        assert grid.delivery == 0

    def test_consumer_battery_charging_with_evcharger(self):
        """Test battery and EV charger both active.

        Scenario: Battery charging while EV charger running
        - PV Production: 8000W
        - Battery charging: 4000W
        - EV Charger: 3000W
        - Grid import: 4500W (supplements PV)
        """
        inverter = InverterPowerflow(
            power=-500, dc_power=8000, battery_discharge=0
        )
        grid = GridPowerflow(power=-4500)
        battery = BatteryPowerflow(power=4000)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=3000, battery=battery
        )

        # house = abs(-4500 - (-500)) - 3000 = 4000 - 3000 = 1000
        assert consumer.house == 1000

        # consumer.inverter = max(0, 500 - 4000) = 0
        assert consumer.inverter == 0

        # Total = house + evcharger + inverter = 1000 + 3000 + 0 = 4000
        assert consumer.total == 4000

    def test_consumer_battery_high_efficiency_charging(self):
        """Test battery charging with very high efficiency (minimal losses).

        Scenario: Modern inverter with high efficiency
        - Grid import: 5100W
        - Inverter consuming: 5010W (AC side)
        - Battery charging: 5000W (DC side)
        - Losses: 10W (99.8% efficiency)
        - House: 100W
        """
        inverter = InverterPowerflow(
            power=-5010, dc_power=0, battery_discharge=0
        )
        grid = GridPowerflow(power=-5110)
        battery = BatteryPowerflow(power=5000)

        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        # house = abs(-5110 - (-5010)) = 100
        assert consumer.house == 100

        # consumer.inverter = max(0, 5010 - 5000) = 10W (losses)
        assert consumer.inverter == 10

        # Total = 100 + 10 = 110
        assert consumer.total == 110


class TestGridPowerflowValidation:
    """Additional validation tests for GridPowerflow."""

    def test_grid_zero_power(self):
        """Test grid with zero power."""
        grid = GridPowerflow(power=0)

        assert grid.consumption == 0
        assert grid.delivery == 0
        assert grid.is_valid is True


class TestBatteryPowerflowValidation:
    """Additional validation tests for BatteryPowerflow."""

    def test_battery_zero_power(self):
        """Test battery with zero power."""
        battery = BatteryPowerflow(power=0)

        assert battery.charge == 0
        assert battery.discharge == 0
        assert battery.is_valid is True


class TestPowerflowPreparePointEnergy:
    """Tests for Powerflow.prepare_point_energy method."""

    def test_prepare_point_energy_without_prices(self):
        """Test prepare_point_energy without prices."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        point = powerflow.prepare_point_energy()

        assert point._name == "energy"

    def test_prepare_point_energy_with_prices(self):
        """Test prepare_point_energy with prices."""
        from solaredge2mqtt.services.energy.settings import PriceSettings

        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=300)  # Delivery = 300
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        prices = PriceSettings(consumption=0.30, delivery=0.08)
        point = powerflow.prepare_point_energy(prices=prices)

        # Check that the point has fields
        assert point._name == "energy"
        # The point should have field pairs added
        assert len(point._fields) > 0

    def test_prepare_point_energy_custom_measurement(self):
        """Test prepare_point_energy with custom measurement name."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=0)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        powerflow = Powerflow(
            pv_production=1200,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        point = powerflow.prepare_point_energy(measurement="custom_energy")

        assert point._name == "custom_energy"


class TestInverterPowerflowFromModbus:
    """Tests for InverterPowerflow.from_modbus method."""

    def test_from_modbus_basic(self):
        """Test from_modbus creates InverterPowerflow correctly."""
        from solaredge2mqtt.services.modbus.models.inverter import (
            ModbusDeviceInfo,
            ModbusInverter,
        )

        # Create mock device info
        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "SE10K",
                "c_version": "1.0.0",
                "c_serialnumber": "INV12345",
            }
        )

        # Create mock inverter data with proper structure
        inverter_data = ModbusInverter(
            device_info,
            {
                "status": 4,  # ON and producing
                "power_ac": 1000,
                "power_ac_scale": 0,
                "current": 10,
                "current_scale": 0,
                "l1_voltage": 230,
                "l2_voltage": 230,
                "l3_voltage": 230,
                "l1n_voltage": 230,
                "l2n_voltage": 230,
                "l3n_voltage": 230,
                "voltage_scale": 0,
                "frequency": 50,
                "frequency_scale": 0,
                "power_apparent": 1100,
                "power_apparent_scale": 0,
                "power_reactive": 50,
                "power_reactive_scale": 0,
                "power_factor": 95,
                "power_factor_scale": -2,
                "energy_total": 50000,
                "energy_total_scale": 0,
                "current_dc": 5,
                "current_dc_scale": 0,
                "voltage_dc": 400,
                "voltage_dc_scale": 0,
                "power_dc": 1200,
                "power_dc_scale": 0,
                "temperature": 35,
                "temperature_scale": 0,
            },
        )

        battery = BatteryPowerflow(power=0)

        result = InverterPowerflow.from_modbus(inverter_data, battery)

        assert result.power == 1000
        assert result.dc_power == 1200
        assert result.battery_discharge == 0


class TestGridPowerflowFromModbus:
    """Tests for GridPowerflow.from_modbus method."""

    def test_from_modbus_with_import_export_meter(self):
        """Test from_modbus with Import/Export meter."""
        from solaredge2mqtt.services.modbus.models.base import ModbusDeviceInfo
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter

        # Create mock device info with Import/Export option
        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Meter",
                "c_version": "1.0.0",
                "c_serialnumber": "MTR12345",
                "c_option": "Export+Import",
            }
        )

        # Create mock meter data with correct field names
        meter_data = {
            "current": 10,
            "l1_current": 10,
            "current_scale": 0,
            "l1_voltage": 230,
            "l1n_voltage": 230,
            "voltage_scale": 0,
            "frequency": 50,
            "frequency_scale": 0,
            "power": 500,
            "power_scale": 0,
            "power_apparent": 550,
            "power_apparent_scale": 0,
            "power_reactive": 50,
            "power_reactive_scale": 0,
            "power_factor": 95,
            "power_factor_scale": -2,
            "export_energy_active": 10000,
            "import_energy_active": 5000,
            "energy_active_scale": 0,
        }

        meter = ModbusMeter(device_info, meter_data)
        meters = {"meter0": meter}

        result = GridPowerflow.from_modbus(meters)

        assert result.power == 500

    def test_from_modbus_empty_meters(self):
        """Test from_modbus with no meters."""
        result = GridPowerflow.from_modbus({})

        assert result.power == 0


class TestBatteryPowerflowFromModbus:
    """Tests for BatteryPowerflow.from_modbus method."""

    def test_from_modbus_empty_batteries(self):
        """Test from_modbus with no batteries."""
        result = BatteryPowerflow.from_modbus({})

        assert result.power == 0


class TestPowerflowFromModbus:
    """Tests for Powerflow.from_modbus method - PV production calculation."""

    def test_from_modbus_negative_dc_power_with_battery_charging(self):
        """Test PV production when dc_power is negative.

        Grid charging battery scenario.
        Scenario: Battery charging from grid + some PV production
        - dc_power: -4493W (AC→DC conversion)
        - battery.charge: 4998W
        - Expected pv_production: 505W (4998 - 4493)
        """
        from solaredge2mqtt.services.modbus.models.base import (
            ModbusDeviceInfo,
        )
        from solaredge2mqtt.services.modbus.models.battery import (
            ModbusBattery,
        )
        from solaredge2mqtt.services.modbus.models.inverter import (
            ModbusInverter,
        )
        from solaredge2mqtt.services.modbus.models.unit import ModbusUnit

        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "SE10K",
                "c_version": "1.0.0",
                "c_serialnumber": "INV12345",
            }
        )

        inverter_data = ModbusInverter(
            device_info,
            {
                "status": 4,
                "power_ac": -4426,
                "power_ac_scale": 0,
                "current": 20,
                "current_scale": 0,
                "l1_voltage": 230,
                "l2_voltage": 230,
                "l3_voltage": 230,
                "l1n_voltage": 230,
                "l2n_voltage": 230,
                "l3n_voltage": 230,
                "voltage_scale": 0,
                "frequency": 50,
                "frequency_scale": -2,
                "power_apparent": 4500,
                "power_apparent_scale": 0,
                "power_reactive": 100,
                "power_reactive_scale": 0,
                "power_factor": 98,
                "power_factor_scale": -2,
                "energy_total": 1000,
                "energy_total_scale": 0,
                "current_dc": 18,
                "current_dc_scale": 0,
                "voltage_dc": 250,
                "voltage_dc_scale": 0,
                "power_dc": -4493,
                "power_dc_scale": 0,
                "temperature": 25,
                "temperature_scale": 0,
            },
        )

        battery_device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Battery",
                "c_version": "1.0.0",
                "c_serialnumber": "BAT12345",
            }
        )

        battery_data = ModbusBattery(
            battery_device_info,
            {
                "status": 3,
                "instantaneous_voltage": 500,
                "instantaneous_current": 10,
                "instantaneous_power": 4998,
                "soe": 50.0,
                "soh": 100.0,
            },
        )

        unit_info = ModbusUnitInfo(
            key="test",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        unit = ModbusUnit(
            info=unit_info,
            inverter=inverter_data,
            meters={},
            batteries={"battery1": battery_data},
        )

        result = Powerflow.from_modbus(unit)

        assert result.pv_production == 505

    def test_from_modbus_positive_dc_power_with_battery_charging(self):
        """Test PV production with positive dc_power and battery charging.

        Scenario: PV only charging, some power to loads/grid
        - dc_power: 1000W
        - battery.charge: 2000W
        - Expected pv_production: 3000W (1000 + 2000)
        """
        from solaredge2mqtt.services.modbus.models.base import (
            ModbusDeviceInfo,
        )
        from solaredge2mqtt.services.modbus.models.battery import (
            ModbusBattery,
        )
        from solaredge2mqtt.services.modbus.models.inverter import (
            ModbusInverter,
        )
        from solaredge2mqtt.services.modbus.models.unit import ModbusUnit

        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "SE10K",
                "c_version": "1.0.0",
                "c_serialnumber": "INV12345",
            }
        )

        inverter_data = ModbusInverter(
            device_info,
            {
                "status": 4,
                "power_ac": 1000,
                "power_ac_scale": 0,
                "current": 5,
                "current_scale": 0,
                "l1_voltage": 230,
                "l2_voltage": 230,
                "l3_voltage": 230,
                "l1n_voltage": 230,
                "l2n_voltage": 230,
                "l3n_voltage": 230,
                "voltage_scale": 0,
                "frequency": 50,
                "frequency_scale": -2,
                "power_apparent": 1100,
                "power_apparent_scale": 0,
                "power_reactive": 50,
                "power_reactive_scale": 0,
                "power_factor": 95,
                "power_factor_scale": -2,
                "energy_total": 1000,
                "energy_total_scale": 0,
                "current_dc": 12,
                "current_dc_scale": 0,
                "voltage_dc": 250,
                "voltage_dc_scale": 0,
                "power_dc": 1000,
                "power_dc_scale": 0,
                "temperature": 25,
                "temperature_scale": 0,
            },
        )

        battery_device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Battery",
                "c_version": "1.0.0",
                "c_serialnumber": "BAT12345",
            }
        )

        battery_data = ModbusBattery(
            battery_device_info,
            {
                "status": 3,
                "instantaneous_voltage": 500,
                "instantaneous_current": 4,
                "instantaneous_power": 2000,
                "soe": 50.0,
                "soh": 100.0,
            },
        )

        unit_info = ModbusUnitInfo(
            key="test",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        unit = ModbusUnit(
            info=unit_info,
            inverter=inverter_data,
            meters={},
            batteries={"battery1": battery_data},
        )

        result = Powerflow.from_modbus(unit)

        assert result.pv_production == 3000

    def test_from_modbus_battery_discharging_with_pv(self):
        """Test PV production with battery discharging.

        Scenario: Battery discharging + PV producing
        - dc_power: 4000W (net DC→AC)
        - battery.discharge: 1000W
        - Expected pv_production: 3000W (4000 - 1000)
        """
        from solaredge2mqtt.services.modbus.models.base import (
            ModbusDeviceInfo,
        )
        from solaredge2mqtt.services.modbus.models.battery import (
            ModbusBattery,
        )
        from solaredge2mqtt.services.modbus.models.inverter import (
            ModbusInverter,
        )
        from solaredge2mqtt.services.modbus.models.unit import ModbusUnit

        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "SE10K",
                "c_version": "1.0.0",
                "c_serialnumber": "INV12345",
            }
        )

        inverter_data = ModbusInverter(
            device_info,
            {
                "status": 4,
                "power_ac": 4000,
                "power_ac_scale": 0,
                "current": 17,
                "current_scale": 0,
                "l1_voltage": 230,
                "l2_voltage": 230,
                "l3_voltage": 230,
                "l1n_voltage": 230,
                "l2n_voltage": 230,
                "l3n_voltage": 230,
                "voltage_scale": 0,
                "frequency": 50,
                "frequency_scale": -2,
                "power_apparent": 4100,
                "power_apparent_scale": 0,
                "power_reactive": 100,
                "power_reactive_scale": 0,
                "power_factor": 98,
                "power_factor_scale": -2,
                "energy_total": 1000,
                "energy_total_scale": 0,
                "current_dc": 16,
                "current_dc_scale": 0,
                "voltage_dc": 250,
                "voltage_dc_scale": 0,
                "power_dc": 4000,
                "power_dc_scale": 0,
                "temperature": 25,
                "temperature_scale": 0,
            },
        )

        battery_device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Battery",
                "c_version": "1.0.0",
                "c_serialnumber": "BAT12345",
            }
        )

        battery_data = ModbusBattery(
            battery_device_info,
            {
                "status": 2,
                "instantaneous_voltage": 500,
                "instantaneous_current": -2,
                "instantaneous_power": -1000,
                "soe": 50.0,
                "soh": 100.0,
            },
        )

        unit_info = ModbusUnitInfo(
            key="test",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        unit = ModbusUnit(
            info=unit_info,
            inverter=inverter_data,
            meters={},
            batteries={"battery1": battery_data},
        )

        result = Powerflow.from_modbus(unit)

        assert result.pv_production == 3000

    def test_from_modbus_pv_only_no_battery_activity(self):
        """Test PV production with no battery activity.

        Scenario: Pure PV production, no battery charging/discharging
        - dc_power: 5000W
        - battery.charge: 0W
        - battery.discharge: 0W
        - Expected pv_production: 5000W
        """
        from solaredge2mqtt.services.modbus.models.base import (
            ModbusDeviceInfo,
        )
        from solaredge2mqtt.services.modbus.models.inverter import (
            ModbusInverter,
        )
        from solaredge2mqtt.services.modbus.models.unit import ModbusUnit

        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "SE10K",
                "c_version": "1.0.0",
                "c_serialnumber": "INV12345",
            }
        )

        inverter_data = ModbusInverter(
            device_info,
            {
                "status": 4,
                "power_ac": 5000,
                "power_ac_scale": 0,
                "current": 22,
                "current_scale": 0,
                "l1_voltage": 230,
                "l2_voltage": 230,
                "l3_voltage": 230,
                "l1n_voltage": 230,
                "l2n_voltage": 230,
                "l3n_voltage": 230,
                "voltage_scale": 0,
                "frequency": 50,
                "frequency_scale": -2,
                "power_apparent": 5100,
                "power_apparent_scale": 0,
                "power_reactive": 100,
                "power_reactive_scale": 0,
                "power_factor": 98,
                "power_factor_scale": -2,
                "energy_total": 1000,
                "energy_total_scale": 0,
                "current_dc": 20,
                "current_dc_scale": 0,
                "voltage_dc": 250,
                "voltage_dc_scale": 0,
                "power_dc": 5000,
                "power_dc_scale": 0,
                "temperature": 25,
                "temperature_scale": 0,
            },
        )

        unit_info = ModbusUnitInfo(
            key="test",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        unit = ModbusUnit(
            info=unit_info,
            inverter=inverter_data,
            meters={},
            batteries={},
        )

        result = Powerflow.from_modbus(unit)

        assert result.pv_production == 5000

    def test_from_modbus_negative_pv_clamped_to_zero(self):
        """Test that negative PV production is clamped to zero.

        Scenario: Edge case where calculation results in negative value
        - dc_power: -5000W
        - battery.charge: 3000W
        - Calculated: -5000 + 3000 = -2000W
        - Expected pv_production: 0W (clamped)
        """
        from solaredge2mqtt.services.modbus.models.base import (
            ModbusDeviceInfo,
        )
        from solaredge2mqtt.services.modbus.models.battery import (
            ModbusBattery,
        )
        from solaredge2mqtt.services.modbus.models.inverter import (
            ModbusInverter,
        )
        from solaredge2mqtt.services.modbus.models.unit import ModbusUnit

        device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "SE10K",
                "c_version": "1.0.0",
                "c_serialnumber": "INV12345",
            }
        )

        inverter_data = ModbusInverter(
            device_info,
            {
                "status": 4,
                "power_ac": -5000,
                "power_ac_scale": 0,
                "current": 22,
                "current_scale": 0,
                "l1_voltage": 230,
                "l2_voltage": 230,
                "l3_voltage": 230,
                "l1n_voltage": 230,
                "l2n_voltage": 230,
                "l3n_voltage": 230,
                "voltage_scale": 0,
                "frequency": 50,
                "frequency_scale": -2,
                "power_apparent": 5100,
                "power_apparent_scale": 0,
                "power_reactive": 100,
                "power_reactive_scale": 0,
                "power_factor": 98,
                "power_factor_scale": -2,
                "energy_total": 1000,
                "energy_total_scale": 0,
                "current_dc": 20,
                "current_dc_scale": 0,
                "voltage_dc": 250,
                "voltage_dc_scale": 0,
                "power_dc": -5000,
                "power_dc_scale": 0,
                "temperature": 25,
                "temperature_scale": 0,
            },
        )

        battery_device_info = ModbusDeviceInfo(
            {
                "c_manufacturer": "SolarEdge",
                "c_model": "Battery",
                "c_version": "1.0.0",
                "c_serialnumber": "BAT12345",
            }
        )

        battery_data = ModbusBattery(
            battery_device_info,
            {
                "status": 3,
                "instantaneous_voltage": 500,
                "instantaneous_current": 6,
                "instantaneous_power": 3000,
                "soe": 50.0,
                "soh": 100.0,
            },
        )

        unit_info = ModbusUnitInfo(
            key="test",
            unit=1,
            role=ModbusUnitRole.LEADER,
        )

        unit = ModbusUnit(
            info=unit_info,
            inverter=inverter_data,
            meters={},
            batteries={"battery1": battery_data},
        )

        result = Powerflow.from_modbus(unit)

        assert result.pv_production == 0


class TestCumulatedPowerflowBugFix:
    """Tests for cumulated powerflow bug fix.

    Tests inverter.pv_production calculation in multi-inverter setups.

    This test class validates the fix for the bug where cumulated powerflow
    had incorrect inverter.pv_production values in multi-inverter setups.

    The issue was that battery_factor = battery_discharge / dc_power was
    incorrectly calculated when summing values first, leading to wrong
    pv_production = production - battery_production calculations.
    """

    def test_cumulated_pv_production_no_battery(self):
        """Test cumulated pv_production equals sum with no battery."""
        # Leader inverter
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid1 = GridPowerflow(power=-200)
        battery1 = BatteryPowerflow(power=0)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            pv_production=1200,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Follower inverter
        inverter2 = InverterPowerflow(
            power=500, dc_power=600, battery_discharge=0
        )
        grid2 = GridPowerflow(power=-100)
        battery2 = BatteryPowerflow(power=0)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            pv_production=600,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Create cumulated powerflow
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # Verify pv_production is correctly summed
        expected_pv_production = (
            inverter1.pv_production + inverter2.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production
        assert cumulated.inverter.pv_production == 1500  # 1000 + 500

        # Verify battery_production is zero
        assert cumulated.inverter.battery_production == 0

        # Verify production equals sum
        assert cumulated.inverter.production == 1500  # 1000 + 500

    def test_cumulated_pv_production_with_battery_discharge(self):
        """Test cumulated pv_production with battery - main bug scenario."""
        # Leader inverter with battery discharge
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=240
        )
        grid1 = GridPowerflow(power=-200)
        battery1 = BatteryPowerflow(power=-240)
        consumer1 = ConsumerPowerflow(
            inverter1, grid1, evcharger=0, battery=battery1
        )

        pf1 = Powerflow(
            # dc_power + battery.charge - battery.discharge
            # = 1200 + 0 - 240
            pv_production=960,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Follower inverter with battery discharge
        inverter2 = InverterPowerflow(
            power=500, dc_power=600, battery_discharge=120
        )
        grid2 = GridPowerflow(power=-100)
        battery2 = BatteryPowerflow(power=-120)
        consumer2 = ConsumerPowerflow(
            inverter2, grid2, evcharger=0, battery=battery2
        )

        pf2 = Powerflow(
            pv_production=480,  # 600 + 0 - 120
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Individual pv_production values
        # inverter1: battery_factor = 240/1200 = 0.2
        #           battery_production = 1000 * 0.2 = 200
        #           pv_production = 1000 - 200 = 800
        # inverter2: battery_factor = 120/600 = 0.2
        #           battery_production = 500 * 0.2 = 100
        #           pv_production = 500 - 100 = 400

        assert inverter1.pv_production == 800
        assert inverter2.pv_production == 400

        # Create cumulated powerflow
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # The bug: without the fix, cumulated would calculate:
        # battery_factor = (240 + 120) / (1200 + 600) = 360 / 1800 = 0.2
        # production = 1000 + 500 = 1500
        # battery_production = 1500 * 0.2 = 300
        # pv_production = 1500 - 300 = 1200 (WRONG!)

        # The fix: should sum individual pv_production values
        expected_pv_production = (
            inverter1.pv_production + inverter2.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production
        assert cumulated.inverter.pv_production == 1200  # 800 + 400

        # Also verify battery_production
        expected_battery_production = (
            inverter1.battery_production + inverter2.battery_production
        )
        assert (
            cumulated.inverter.battery_production
            == expected_battery_production
        )
        assert cumulated.inverter.battery_production == 300  # 200 + 100

    def test_cumulated_pv_production_user_report_scenario(self):
        """Test exact user report scenario.

        Leader consuming, follower producing.
        """
        # Leader inverter - consuming (negative power)
        inverter_leader = InverterPowerflow(
            power=-100, dc_power=0, battery_discharge=0
        )
        grid_leader = GridPowerflow(power=-100)
        battery_leader = BatteryPowerflow(power=0)
        consumer_leader = ConsumerPowerflow(
            inverter_leader, grid_leader, evcharger=0
        )

        pf_leader = Powerflow(
            pv_production=0,
            inverter=inverter_leader,
            grid=grid_leader,
            battery=battery_leader,
            consumer=consumer_leader,
        )

        # Follower inverter - producing
        inverter_follower = InverterPowerflow(
            power=1069, dc_power=1200, battery_discharge=200
        )
        grid_follower = GridPowerflow(power=0)
        battery_follower = BatteryPowerflow(power=-200)
        consumer_follower = ConsumerPowerflow(
            inverter_follower,
            grid_follower,
            evcharger=0,
            battery=battery_follower,
        )

        pf_follower = Powerflow(
            # dc_power + 0 - battery_discharge = 1200 - 200
            pv_production=1000,
            inverter=inverter_follower,
            grid=grid_follower,
            battery=battery_follower,
            consumer=consumer_follower,
        )

        # Individual pv_production values
        # Leader: power=-100, so production=0, pv_production=0
        # Follower: battery_factor = 200/1200 = 0.1667
        #   battery_production = round(1069 * 0.1667)
        #                      = round(178.14) = 178
        #   pv_production = 1069 - 178 = 891

        assert inverter_leader.pv_production == 0
        assert inverter_follower.pv_production == 891

        # Create cumulated powerflow
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf_leader, "follower": pf_follower}
        )

        # Expected: sum of individual pv_production = 0 + 891 = 891
        expected_pv_production = (
            inverter_leader.pv_production + inverter_follower.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production
        assert cumulated.inverter.pv_production == 891

        # Verify it's NOT 429 (the bug value from user report)
        assert cumulated.inverter.pv_production != 429

    def test_cumulated_pv_production_different_battery_factors(self):
        """Test cumulated pv_production with different battery factors."""
        # Inverter 1: High battery factor (40% battery discharge)
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1000, battery_discharge=400
        )
        grid1 = GridPowerflow(power=0)
        battery1 = BatteryPowerflow(power=-400)
        consumer1 = ConsumerPowerflow(
            inverter1, grid1, evcharger=0, battery=battery1
        )

        pf1 = Powerflow(
            pv_production=600,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Inverter 2: Low battery factor (10% battery discharge)
        inverter2 = InverterPowerflow(
            power=1000, dc_power=1000, battery_discharge=100
        )
        grid2 = GridPowerflow(power=0)
        battery2 = BatteryPowerflow(power=-100)
        consumer2 = ConsumerPowerflow(
            inverter2, grid2, evcharger=0, battery=battery2
        )

        pf2 = Powerflow(
            pv_production=900,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Individual calculations:
        # inverter1: battery_factor = 400/1000 = 0.4
        #           battery_production = 1000 * 0.4 = 400
        #           pv_production = 1000 - 400 = 600
        # inverter2: battery_factor = 100/1000 = 0.1
        #           battery_production = 1000 * 0.1 = 100
        #           pv_production = 1000 - 100 = 900

        assert inverter1.pv_production == 600
        assert inverter2.pv_production == 900

        # Create cumulated powerflow
        cumulated = Powerflow.cumulated_powerflow({"inv1": pf1, "inv2": pf2})

        # Without fix: battery_factor = (400+100)/(1000+1000)
        #                              = 500/2000 = 0.25
        #              production = 2000
        #              battery_production = 2000 * 0.25 = 500
        #              pv_production = 2000 - 500 = 1500
        #              (CORRECT by coincidence!)

        # With fix: sum of individual pv_production
        expected_pv_production = (
            inverter1.pv_production + inverter2.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production
        assert cumulated.inverter.pv_production == 1500  # 600 + 900

        # Verify battery_production
        expected_battery_production = (
            inverter1.battery_production + inverter2.battery_production
        )
        assert (
            cumulated.inverter.battery_production
            == expected_battery_production
        )
        assert cumulated.inverter.battery_production == 500  # 400 + 100

    def test_cumulated_pv_production_three_inverters(self):
        """Test cumulated pv_production with three inverters."""
        # Create three inverters with different characteristics
        inverters_data = [
            {"power": 800, "dc_power": 1000, "battery_discharge": 200},
            {"power": 1200, "dc_power": 1500, "battery_discharge": 300},
            {"power": 600, "dc_power": 800, "battery_discharge": 100},
        ]

        powerflows = {}
        individual_pv_productions = []
        individual_battery_productions = []

        for idx, data in enumerate(inverters_data):
            inverter = InverterPowerflow(
                power=data["power"],
                dc_power=data["dc_power"],
                battery_discharge=data["battery_discharge"],
            )
            grid = GridPowerflow(power=0)
            battery = BatteryPowerflow(power=-data["battery_discharge"])
            consumer = ConsumerPowerflow(
                inverter, grid, evcharger=0, battery=battery
            )

            pf = Powerflow(
                pv_production=data["dc_power"] - data["battery_discharge"],
                inverter=inverter,
                grid=grid,
                battery=battery,
                consumer=consumer,
            )

            powerflows[f"inv{idx}"] = pf
            individual_pv_productions.append(inverter.pv_production)
            individual_battery_productions.append(inverter.battery_production)

        # Create cumulated powerflow
        cumulated = Powerflow.cumulated_powerflow(powerflows)

        # Verify pv_production is sum of individual values
        expected_pv_production = sum(individual_pv_productions)
        assert cumulated.inverter.pv_production == expected_pv_production

        # Verify battery_production is sum of individual values
        expected_battery_production = sum(individual_battery_productions)
        assert (
            cumulated.inverter.battery_production
            == expected_battery_production
        )

        # Verify production equals sum
        expected_production = sum(data["power"] for data in inverters_data)
        assert cumulated.inverter.production == expected_production

    def test_cumulated_preserves_single_inverter_behavior(self):
        """Test cumulated powerflow with single inverter."""
        # Create single inverter powerflow
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=240
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=-240)
        consumer = ConsumerPowerflow(
            inverter, grid, evcharger=0, battery=battery
        )

        pf = Powerflow(
            pv_production=960,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        # Create cumulated with single powerflow
        cumulated = Powerflow.cumulated_powerflow({"single": pf})

        # Verify all values match the original
        assert cumulated.inverter.power == inverter.power
        assert cumulated.inverter.dc_power == inverter.dc_power
        assert cumulated.inverter.production == inverter.production
        assert cumulated.inverter.pv_production == inverter.pv_production
        assert (
            cumulated.inverter.battery_production
            == inverter.battery_production
        )
        assert cumulated.pv_production == pf.pv_production

    def test_explicit_values_override_computed_values(self):
        """Test that explicit values correctly override computed properties."""
        # Create inverter with normal values
        inverter = InverterPowerflow(
            power=1000,
            dc_power=1200,
            battery_discharge=200,
        )

        # Set explicit values
        inverter._explicit_production = 1500
        inverter._explicit_battery_production = 400
        inverter._explicit_pv_production = 1100

        # Verify explicit values are used
        assert inverter.production == 1500
        assert inverter.battery_production == 400
        assert inverter.pv_production == 1100

        # Verify they don't match computed values
        # Without explicit values: production would be 1000,
        # battery_production ~167, pv_production ~833
        assert inverter.production != 1000

    def test_cumulated_with_zero_dc_power(self):
        """Test cumulated powerflow when some inverters have zero dc_power."""
        # Inverter 1: Normal operation
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=200
        )
        grid1 = GridPowerflow(power=0)
        battery1 = BatteryPowerflow(power=-200)
        consumer1 = ConsumerPowerflow(
            inverter1, grid1, evcharger=0, battery=battery1
        )

        pf1 = Powerflow(
            pv_production=1000,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Inverter 2: Zero dc_power (night time or consuming)
        inverter2 = InverterPowerflow(
            power=-50, dc_power=0, battery_discharge=0
        )
        grid2 = GridPowerflow(power=-50)
        battery2 = BatteryPowerflow(power=0)
        consumer2 = ConsumerPowerflow(
            inverter2, grid2, evcharger=0, battery=battery2
        )

        pf2 = Powerflow(
            pv_production=0,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Create cumulated powerflow
        cumulated = Powerflow.cumulated_powerflow({"inv1": pf1, "inv2": pf2})

        # Verify pv_production is correctly summed
        expected_pv_production = (
            inverter1.pv_production + inverter2.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production

        # Verify it handles division by zero safely
        assert cumulated.inverter.battery_factor >= 0  # Should not crash
