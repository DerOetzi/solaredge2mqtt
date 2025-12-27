"""Tests for powerflow models - additional tests for better coverage."""

import pytest

from solaredge2mqtt.services.modbus.models.base import ModbusUnitInfo, ModbusUnitRole
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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

        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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

        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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

        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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

        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter1 = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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

        inverter2 = InverterPowerflow(power=500, dc_power=600, battery_discharge=0)
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

        cumulated = Powerflow.cumulated_powerflow({"leader": pf1, "follower": pf2})

        assert cumulated.pv_production == 1800  # 1200 + 600
        assert cumulated.inverter.power == 1500  # 1000 + 500
        assert cumulated.unit.role == ModbusUnitRole.CUMULATED

    def test_powerflow_is_not_valid_with_last_first_call(self):
        """Test is_not_valid_with_last on first call."""
        # Reset class variable
        Powerflow.last_powerflow = None

        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter_last = InverterPowerflow(power=0, dc_power=0, battery_discharge=0)
        grid_last = GridPowerflow(power=0)
        battery_last = BatteryPowerflow(power=0)
        consumer_last = ConsumerPowerflow(inverter_last, grid_last, evcharger=0)

        last_powerflow = Powerflow(
            pv_production=0,
            inverter=inverter_last,
            grid=grid_last,
            battery=battery_last,
            consumer=consumer_last,
        )
        Powerflow.last_powerflow = last_powerflow

        # Current powerflow with sudden increase > 100
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=100, dc_power=50, battery_discharge=100)

        # battery_factor = 100 / 50 = 2.0
        # battery_production = round(100 * 2.0) = 200 -> capped at 100
        assert inverter.battery_production <= inverter.production


class TestConsumerPowerflowValidation:
    """Additional validation tests for ConsumerPowerflow."""

    def test_consumer_used_battery_production_capped(self):
        """Test used_battery_production is capped at used_production."""
        inverter = InverterPowerflow(power=100, dc_power=50, battery_discharge=100)
        grid = GridPowerflow(power=0)

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # used_battery_production should not exceed used_production
        assert consumer.used_battery_production <= consumer.used_production

    def test_consumer_used_production_exceeds_grid_delivery(self):
        """Test used_production when production exceeds grid delivery."""
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
        grid = GridPowerflow(power=300)  # Delivering 300 to grid

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # used_production = production - grid.delivery = 1000 - 300 = 700
        assert consumer.used_production == 700

    def test_consumer_used_production_when_production_less_than_delivery(self):
        """Test used_production is 0 when production <= grid delivery."""
        inverter = InverterPowerflow(power=200, dc_power=250, battery_discharge=0)
        grid = GridPowerflow(power=300)  # Delivering more than production

        consumer = ConsumerPowerflow(inverter, grid, evcharger=0)

        # production (200) < grid.delivery (300), so used_production = 0
        assert consumer.used_production == 0


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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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

        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        inverter = InverterPowerflow(power=1000, dc_power=1200, battery_discharge=0)
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
        from solaredge2mqtt.services.modbus.models.inverter import ModbusInverter, ModbusDeviceInfo

        # Create mock device info
        device_info = ModbusDeviceInfo({
            "c_manufacturer": "SolarEdge",
            "c_model": "SE10K",
            "c_version": "1.0.0",
            "c_serialnumber": "INV12345",
        })

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
            }
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
        from solaredge2mqtt.services.modbus.models.meter import ModbusMeter
        from solaredge2mqtt.services.modbus.models.base import ModbusDeviceInfo

        # Create mock device info with Import/Export option
        device_info = ModbusDeviceInfo({
            "c_manufacturer": "SolarEdge",
            "c_model": "Meter",
            "c_version": "1.0.0",
            "c_serialnumber": "MTR12345",
            "c_option": "Export+Import",
        })

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
