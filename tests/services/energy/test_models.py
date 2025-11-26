"""Tests for energy models module."""

from datetime import datetime, timezone

from solaredge2mqtt.services.energy.models import (
    BatteryEnergy,
    ConsumerEnergy,
    GridEnergy,
    HistoricEnergy,
    HistoricInfo,
    HistoricMoney,
    HistoricPeriod,
    HistoricQuery,
    InverterEnergy,
)


class TestHistoricQuery:
    """Tests for HistoricQuery enum."""

    def test_actual_query(self):
        """Test ACTUAL query."""
        assert str(HistoricQuery.ACTUAL) == "actual_unit"
        assert HistoricQuery.ACTUAL.query == "actual_unit"

    def test_last_query(self):
        """Test LAST query."""
        assert str(HistoricQuery.LAST) == "historic_unit"
        assert HistoricQuery.LAST.query == "historic_unit"


class TestHistoricPeriod:
    """Tests for HistoricPeriod enum."""

    def test_today_period(self):
        """Test TODAY period."""
        period = HistoricPeriod.TODAY
        assert period.topic == "today"
        assert period.title == "Today"
        assert period.unit == "1d"
        assert period.query == HistoricQuery.ACTUAL
        assert period.auto_discovery is True

    def test_yesterday_period(self):
        """Test YESTERDAY period."""
        period = HistoricPeriod.YESTERDAY
        assert period.topic == "yesterday"
        assert period.title == "Yesterday"
        assert period.unit == "1d"
        assert period.query == HistoricQuery.LAST
        assert period.auto_discovery is True

    def test_this_week_period(self):
        """Test THIS_WEEK period."""
        period = HistoricPeriod.THIS_WEEK
        assert period.topic == "this_week"
        assert period.title == "This week"
        assert period.unit == "1w"
        assert period.query == HistoricQuery.ACTUAL
        assert period.auto_discovery is False

    def test_last_month_period(self):
        """Test LAST_MONTH period."""
        period = HistoricPeriod.LAST_MONTH
        assert period.topic == "last_month"
        assert period.title == "Last month"
        assert period.unit == "1mo"
        assert period.query == HistoricQuery.LAST
        assert period.auto_discovery is True

    def test_lifetime_period(self):
        """Test LIFETIME period."""
        period = HistoricPeriod.LIFETIME
        assert period.topic == "lifetime"
        assert period.title == "Lifetime"
        assert period.unit == "99y"
        assert period.query == HistoricQuery.ACTUAL
        assert period.auto_discovery is True


class TestHistoricInfo:
    """Tests for HistoricInfo class."""

    def test_historic_info_creation(self):
        """Test HistoricInfo creation."""
        info = HistoricInfo(
            unit="leader",
            period=HistoricPeriod.TODAY,
            start=datetime(2024, 6, 15, 0, 0, tzinfo=timezone.utc),
            stop=datetime(2024, 6, 15, 23, 59, tzinfo=timezone.utc),
        )

        assert info.unit == "leader"
        assert info.period == HistoricPeriod.TODAY

    def test_historic_info_without_unit(self):
        """Test HistoricInfo without unit."""
        info = HistoricInfo(
            period=HistoricPeriod.TODAY,
            start=datetime(2024, 6, 15, 0, 0, tzinfo=timezone.utc),
            stop=datetime(2024, 6, 15, 23, 59, tzinfo=timezone.utc),
        )

        assert info.unit is None


class TestHistoricMoney:
    """Tests for HistoricMoney class."""

    def test_historic_money_creation(self):
        """Test HistoricMoney creation."""
        money = HistoricMoney(
            delivered=50.0,
            saved=30.0,
            consumed=20.0,
            price_in=0.30,
            price_out=0.08,
        )

        assert money.delivered == 50.0
        assert money.saved == 30.0
        assert money.consumed == 20.0

    def test_historic_money_balance_grid(self):
        """Test balance_grid computed field."""
        money = HistoricMoney(
            delivered=50.0,
            saved=30.0,
            consumed=20.0,
            price_in=0.30,
            price_out=0.08,
        )

        assert money.balance_grid == 30.0  # 50.0 - 20.0

    def test_historic_money_balance_total(self):
        """Test balance_total computed field."""
        money = HistoricMoney(
            delivered=50.0,
            saved=30.0,
            consumed=20.0,
            price_in=0.30,
            price_out=0.08,
        )

        assert money.balance_total == 60.0  # 30.0 + 30.0

    def test_historic_money_total_revenue(self):
        """Test total_revenue computed field."""
        money = HistoricMoney(
            delivered=50.0,
            saved=30.0,
            consumed=20.0,
            price_in=0.30,
            price_out=0.08,
        )

        assert money.total_revenue == 80.0  # 50.0 + 30.0


class TestInverterEnergy:
    """Tests for InverterEnergy class."""

    def test_inverter_energy_creation(self):
        """Test InverterEnergy creation."""
        inverter = InverterEnergy(
            production=100.0,
            consumption=10.0,
            dc_power=5000.0,
            pv_production=80.0,
            battery_production=20.0,
        )

        assert inverter.production == 100.0
        assert inverter.consumption == 10.0
        assert inverter.dc_power == 5000.0
        assert inverter.pv_production == 80.0
        assert inverter.battery_production == 20.0


class TestGridEnergy:
    """Tests for GridEnergy class."""

    def test_grid_energy_creation(self):
        """Test GridEnergy creation."""
        grid = GridEnergy(
            delivery=30.0,
            consumption=10.0,
        )

        assert grid.delivery == 30.0
        assert grid.consumption == 10.0


class TestBatteryEnergy:
    """Tests for BatteryEnergy class."""

    def test_battery_energy_creation(self):
        """Test BatteryEnergy creation."""
        battery = BatteryEnergy(
            charge=15.0,
            discharge=20.0,
        )

        assert battery.charge == 15.0
        assert battery.discharge == 20.0


class TestConsumerEnergy:
    """Tests for ConsumerEnergy class."""

    def test_consumer_energy_creation(self):
        """Test ConsumerEnergy creation."""
        consumer = ConsumerEnergy(
            house=60.0,
            evcharger=10.0,
            inverter=5.0,
            total=75.0,
            used_production=70.0,
            used_pv_production=50.0,
            used_battery_production=20.0,
        )

        assert consumer.house == 60.0
        assert consumer.evcharger == 10.0
        assert consumer.inverter == 5.0
        assert consumer.total == 75.0
        assert consumer.used_production == 70.0
        assert consumer.used_pv_production == 50.0
        assert consumer.used_battery_production == 20.0


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


class TestSelfConsumptionRate:
    """Tests for SelfConsumptionRate class."""

    def test_self_consumption_with_production(self):
        """Test self consumption rate with production."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        rate = energy.self_consumption_rates

        assert isinstance(rate.grid, int)
        assert isinstance(rate.battery, int)
        assert isinstance(rate.pv, int)
        assert isinstance(rate.total, int)

    def test_self_consumption_no_production(self):
        """Test self consumption rate with no production."""
        data = make_historic_energy_data()
        data["inverter_production"] = 0.0
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        rate = energy.self_consumption_rates

        assert rate.grid == 0
        assert rate.battery == 0
        assert rate.pv == 0
        assert rate.total == 0


class TestSelfSufficiencyRate:
    """Tests for SelfSufficiencyRate class."""

    def test_self_sufficiency_with_consumption(self):
        """Test self sufficiency rate with consumption."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        rate = energy.self_sufficiency_rates

        assert isinstance(rate.grid, int)
        assert isinstance(rate.battery, int)
        assert isinstance(rate.pv, int)
        assert isinstance(rate.total, int)

    def test_self_sufficiency_no_consumption(self):
        """Test self sufficiency rate with no consumption."""
        data = make_historic_energy_data()
        data["consumer_total"] = 0.0
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        rate = energy.self_sufficiency_rates

        assert rate.grid == 0
        assert rate.battery == 0
        assert rate.pv == 0
        assert rate.total == 0


class TestHistoricEnergy:
    """Tests for HistoricEnergy class."""

    def test_historic_energy_creation(self):
        """Test HistoricEnergy creation."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        assert energy.pv_production == 100.0
        assert energy.inverter.production == 100.0
        assert energy.grid.delivery == 30.0
        assert energy.battery.charge == 15.0
        assert energy.consumer.house == 50.0

    def test_historic_energy_mqtt_topic_without_unit(self):
        """Test mqtt_topic without unit."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        topic = energy.mqtt_topic()

        assert topic == "energy/today"

    def test_historic_energy_mqtt_topic_with_unit(self):
        """Test mqtt_topic with unit."""
        data = make_historic_energy_data()
        data["unit"] = "leader"
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        topic = energy.mqtt_topic()

        assert topic == "energy/leader/today"

    def test_historic_energy_str(self):
        """Test __str__ method."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        assert str(energy) == "energy: today"

    def test_historic_energy_with_money(self):
        """Test HistoricEnergy with money data."""
        data = make_historic_energy_data()
        data["money_delivered"] = 50.0
        data["money_saved"] = 30.0
        data["money_consumed"] = 20.0
        data["money_price_in"] = 0.30
        data["money_price_out"] = 0.08

        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        assert energy.money is not None
        assert energy.money.delivered == 50.0

    def test_historic_energy_homeassistant_device_info(self):
        """Test homeassistant_device_info method."""
        data = make_historic_energy_data()
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        ha_info = energy.homeassistant_device_info()

        assert "Energy" in ha_info["name"]
        assert "Today" in ha_info["name"]

    def test_historic_energy_homeassistant_device_info_with_unit(self):
        """Test homeassistant_device_info with unit."""
        data = make_historic_energy_data()
        data["unit"] = "leader"
        energy = HistoricEnergy(data, HistoricPeriod.TODAY)

        ha_info = energy.homeassistant_device_info()

        assert "Energy" in ha_info["name"]
        assert "leader" in ha_info["name"]
        assert "Today" in ha_info["name"]
