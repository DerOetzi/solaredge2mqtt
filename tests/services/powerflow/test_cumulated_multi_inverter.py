"""Tests for multi-inverter cumulated powerflow calculations.

This test module specifically validates the fix for the bug where cumulated
inverter.pv_production did not equal the sum of individual inverter values
in multi-inverter configurations with battery discharge.
"""


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


class TestMultiInverterCumulation:
    """Tests for multi-inverter cumulated powerflow calculations."""

    def test_cumulated_without_battery_discharge(self):
        """Test cumulation without battery discharge (simple case)."""
        # Leader inverter: 1000W AC, 1200W DC, no battery
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

        # Follower inverter: 500W AC, 600W DC, no battery
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

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # Verify cumulated values
        assert cumulated.inverter.production == 1500  # 1000 + 500
        assert cumulated.inverter.consumption == 0  # 0 + 0
        assert (
            cumulated.inverter.battery_production == 0
        )  # 0 + 0 (no battery)
        assert cumulated.inverter.pv_production == 1500  # 1000 + 500

    def test_cumulated_with_battery_discharge_scenario_from_issue(self):
        """Test the exact scenario reported in the issue.

        Leader: 0W production (nighttime), no battery discharge
        Follower: 1069W production, battery discharge creates wrong ratio
        Expected cumulated pv_production: 1069W
        Actual (before fix): 429W (incorrect!)
        """
        # Leader inverter: 0W production (nighttime)
        inverter1 = InverterPowerflow(
            power=0, dc_power=0, battery_discharge=0
        )
        grid1 = GridPowerflow(power=0)
        battery1 = BatteryPowerflow(power=0)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            pv_production=0,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Follower inverter: 1069W production with battery discharge
        # DC power: 1669W, battery discharge: 600W
        # Battery factor: 600/1669 = 0.3594
        # Battery production: round(1069 * 0.3594) = 384W
        # PV production: 1069 - 384 = 685W
        inverter2 = InverterPowerflow(
            power=1069, dc_power=1669, battery_discharge=600
        )
        grid2 = GridPowerflow(power=0)
        battery2 = BatteryPowerflow(power=-600)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            # DC power - battery charge + battery discharge
            pv_production=1069,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # REQ-1: Cumulated inverter.pv_production MUST equal sum of
        # individual values
        expected_pv_production = (
            pf1.inverter.pv_production + pf2.inverter.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production

        # REQ-2: Cumulated inverter.battery_production MUST equal sum of
        # individual values
        expected_battery_production = (
            pf1.inverter.battery_production + pf2.inverter.battery_production
        )
        assert (
            cumulated.inverter.battery_production
            == expected_battery_production
        )

        # REQ-3: Cumulated inverter.production MUST equal sum of individual
        # values
        expected_production = (
            pf1.inverter.production + pf2.inverter.production
        )
        assert cumulated.inverter.production == expected_production

        # REQ-4: Cumulated inverter.consumption MUST equal sum of individual
        # values
        expected_consumption = (
            pf1.inverter.consumption + pf2.inverter.consumption
        )
        assert cumulated.inverter.consumption == expected_consumption

        # REQ-5: Maintain mathematical consistency
        assert (
            cumulated.inverter.pv_production
            + cumulated.inverter.battery_production
            == cumulated.inverter.production
        )

    def test_cumulated_both_inverters_with_battery_discharge(self):
        """Test cumulation when both inverters have battery discharge."""
        # Leader inverter: 1000W production, 200W battery discharge
        # DC power: 1200W, battery discharge: 200W
        # Battery factor: 200/1200 = 0.1667
        # Battery production: round(1000 * 0.1667) = 167W
        # PV production: 1000 - 167 = 833W
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=200
        )
        grid1 = GridPowerflow(power=-200)
        battery1 = BatteryPowerflow(power=-200)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            pv_production=1000,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Follower inverter: 800W production, 300W battery discharge
        # DC power: 1100W, battery discharge: 300W
        # Battery factor: 300/1100 = 0.2727
        # Battery production: round(800 * 0.2727) = 218W
        # PV production: 800 - 218 = 582W
        inverter2 = InverterPowerflow(
            power=800, dc_power=1100, battery_discharge=300
        )
        grid2 = GridPowerflow(power=-100)
        battery2 = BatteryPowerflow(power=-300)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            pv_production=800,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # Verify all requirements
        # REQ-1: PV production
        expected_pv_production = (
            pf1.inverter.pv_production + pf2.inverter.pv_production
        )
        assert cumulated.inverter.pv_production == expected_pv_production

        # REQ-2: Battery production
        expected_battery_production = (
            pf1.inverter.battery_production + pf2.inverter.battery_production
        )
        assert (
            cumulated.inverter.battery_production
            == expected_battery_production
        )

        # REQ-3: Production
        expected_production = (
            pf1.inverter.production + pf2.inverter.production
        )
        assert cumulated.inverter.production == expected_production

        # REQ-4: Consumption
        expected_consumption = (
            pf1.inverter.consumption + pf2.inverter.consumption
        )
        assert cumulated.inverter.consumption == expected_consumption

        # REQ-5: Mathematical consistency
        assert (
            cumulated.inverter.pv_production
            + cumulated.inverter.battery_production
            == cumulated.inverter.production
        )

    def test_cumulated_negative_power_consumption(self):
        """Test cumulation with inverters consuming power (nighttime)."""
        # Leader inverter: consuming 50W
        inverter1 = InverterPowerflow(
            power=-50, dc_power=0, battery_discharge=0
        )
        grid1 = GridPowerflow(power=-50)
        battery1 = BatteryPowerflow(power=0)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            pv_production=0,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Follower inverter: consuming 30W
        inverter2 = InverterPowerflow(
            power=-30, dc_power=0, battery_discharge=0
        )
        grid2 = GridPowerflow(power=-30)
        battery2 = BatteryPowerflow(power=0)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            pv_production=0,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # Verify consumption is summed correctly
        assert cumulated.inverter.consumption == 80  # 50 + 30
        assert cumulated.inverter.production == 0
        assert cumulated.inverter.battery_production == 0
        assert cumulated.inverter.pv_production == 0

    def test_cumulated_mixed_production_consumption(self):
        """Test cumulation with one producing and one consuming."""
        # Leader inverter: producing 500W
        inverter1 = InverterPowerflow(
            power=500, dc_power=600, battery_discharge=0
        )
        grid1 = GridPowerflow(power=200)
        battery1 = BatteryPowerflow(power=0)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            pv_production=600,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        # Follower inverter: consuming 100W (nighttime)
        inverter2 = InverterPowerflow(
            power=-100, dc_power=0, battery_discharge=0
        )
        grid2 = GridPowerflow(power=-100)
        battery2 = BatteryPowerflow(power=0)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            pv_production=0,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # Verify cumulated values match sum of individual values
        # power = 500 + (-100) = 400 (net power output)
        assert cumulated.inverter.power == 400

        # Production and consumption should be summed from individuals
        expected_production = (
            pf1.inverter.production + pf2.inverter.production
        )  # 500 + 0 = 500
        expected_consumption = (
            pf1.inverter.consumption + pf2.inverter.consumption
        )  # 0 + 100 = 100
        
        assert cumulated.inverter.production == expected_production
        assert cumulated.inverter.consumption == expected_consumption
        assert cumulated.inverter.pv_production == expected_production
        assert cumulated.inverter.battery_production == 0  # 0 + 0

    def test_cumulated_with_three_inverters(self):
        """Test cumulation with three inverters (edge case)."""
        # Create three powerflows
        powerflows = {}

        for i, (power, dc_power, discharge) in enumerate(
            [(1000, 1200, 100), (800, 1000, 50), (600, 700, 0)], start=1
        ):
            inverter = InverterPowerflow(
                power=power, dc_power=dc_power, battery_discharge=discharge
            )
            grid = GridPowerflow(power=0)
            battery = BatteryPowerflow(power=-discharge)
            consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

            powerflows[f"inv{i}"] = Powerflow(
                pv_production=dc_power,
                inverter=inverter,
                grid=grid,
                battery=battery,
                consumer=consumer,
            )

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(powerflows)

        # Calculate expected values
        expected_production = sum(
            pf.inverter.production for pf in powerflows.values()
        )
        expected_pv_production = sum(
            pf.inverter.pv_production for pf in powerflows.values()
        )
        expected_battery_production = sum(
            pf.inverter.battery_production for pf in powerflows.values()
        )

        # Verify
        assert cumulated.inverter.production == expected_production
        assert cumulated.inverter.pv_production == expected_pv_production
        assert (
            cumulated.inverter.battery_production
            == expected_battery_production
        )

        # Verify mathematical consistency
        assert (
            cumulated.inverter.pv_production
            + cumulated.inverter.battery_production
            == cumulated.inverter.production
        )

    def test_cumulated_single_inverter_backward_compatibility(self):
        """Test that single-inverter cumulation still works correctly."""
        # Single inverter with battery discharge
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=200
        )
        grid = GridPowerflow(power=-200)
        battery = BatteryPowerflow(power=-200)
        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        pf = Powerflow(
            pv_production=1000,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )

        # Cumulate with single inverter
        cumulated = Powerflow.cumulated_powerflow({"single": pf})

        # Values should match original
        assert cumulated.inverter.production == pf.inverter.production
        assert cumulated.inverter.consumption == pf.inverter.consumption
        assert (
            cumulated.inverter.battery_production
            == pf.inverter.battery_production
        )
        assert cumulated.inverter.pv_production == pf.inverter.pv_production

    def test_cumulated_role_is_cumulated(self):
        """Test that cumulated powerflow has CUMULATED role."""
        inverter1 = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=0
        )
        grid1 = GridPowerflow(power=0)
        battery1 = BatteryPowerflow(power=0)
        consumer1 = ConsumerPowerflow(inverter1, grid1, evcharger=0)

        pf1 = Powerflow(
            unit=ModbusUnitInfo(
                key="leader", unit=1, role=ModbusUnitRole.LEADER
            ),
            pv_production=1200,
            inverter=inverter1,
            grid=grid1,
            battery=battery1,
            consumer=consumer1,
        )

        inverter2 = InverterPowerflow(
            power=500, dc_power=600, battery_discharge=0
        )
        grid2 = GridPowerflow(power=0)
        battery2 = BatteryPowerflow(power=0)
        consumer2 = ConsumerPowerflow(inverter2, grid2, evcharger=0)

        pf2 = Powerflow(
            unit=ModbusUnitInfo(
                key="follower", unit=2, role=ModbusUnitRole.FOLLOWER
            ),
            pv_production=600,
            inverter=inverter2,
            grid=grid2,
            battery=battery2,
            consumer=consumer2,
        )

        # Cumulate
        cumulated = Powerflow.cumulated_powerflow(
            {"leader": pf1, "follower": pf2}
        )

        # Verify unit info
        assert cumulated.unit.role == ModbusUnitRole.CUMULATED
        assert cumulated.unit.key == "cumulated"
        assert cumulated.unit.unit == 0


class TestInverterPowerflowOverrides:
    """Test override mechanism for computed fields."""

    def test_override_production(self):
        """Test that production override works."""
        inverter = InverterPowerflow(
            power=1000,
            dc_power=1200,
            battery_discharge=0,
            override_production=999,
        )

        # Override should be used
        assert inverter.production == 999
        # Not the calculated value
        assert inverter.production != 1000

    def test_override_consumption(self):
        """Test that consumption override works."""
        inverter = InverterPowerflow(
            power=-500,
            dc_power=0,
            battery_discharge=0,
            override_consumption=600,
        )

        # Override should be used
        assert inverter.consumption == 600
        # Not the calculated value
        assert inverter.consumption != 500

    def test_override_battery_production(self):
        """Test that battery_production override works."""
        inverter = InverterPowerflow(
            power=1000,
            dc_power=1200,
            battery_discharge=200,
            override_battery_production=250,
        )

        # Override should be used
        assert inverter.battery_production == 250
        # Not the calculated value from battery_factor
        calculated = int(round(1000 * (200 / 1200)))
        assert inverter.battery_production != calculated

    def test_override_pv_production(self):
        """Test that pv_production override works."""
        inverter = InverterPowerflow(
            power=1000,
            dc_power=1200,
            battery_discharge=200,
            override_pv_production=750,
        )

        # Override should be used
        assert inverter.pv_production == 750

    def test_no_override_uses_computed_values(self):
        """Test that without overrides, computed values are used."""
        inverter = InverterPowerflow(
            power=1000, dc_power=1200, battery_discharge=200
        )

        # Should use computed values
        assert inverter.production == 1000
        assert inverter.consumption == 0
        battery_factor = 200 / 1200
        expected_battery = int(round(1000 * battery_factor))
        assert inverter.battery_production == expected_battery
        assert inverter.pv_production == 1000 - expected_battery
