"""Tests for energy settings module."""

import pytest

from solaredge2mqtt.services.energy.settings import EnergySettings, PriceSettings


class TestPriceSettings:
    """Tests for PriceSettings class."""

    def test_price_settings_defaults(self):
        """Test PriceSettings default values."""
        settings = PriceSettings()

        assert settings.consumption is None
        assert settings.delivery is None
        assert settings.currency is None

    def test_price_settings_custom_values(self):
        """Test PriceSettings with custom values."""
        settings = PriceSettings(
            consumption=0.30,
            delivery=0.08,
            currency="EUR",
        )

        assert settings.consumption == pytest.approx(0.30)
        assert settings.delivery == pytest.approx(0.08)
        assert settings.currency == "EUR"

    def test_price_settings_is_configured_true_consumption_only(self):
        """Test is_configured when only consumption is set."""
        settings = PriceSettings(consumption=0.30, currency="EUR")

        assert settings.is_configured is True

    def test_price_settings_is_configured_true_delivery_only(self):
        """Test is_configured when only delivery is set."""
        settings = PriceSettings(delivery=0.08, currency="EUR")

        assert settings.is_configured is True

    def test_price_settings_is_configured_true_both(self):
        """Test is_configured when both prices are set."""
        settings = PriceSettings(
            consumption=0.30,
            delivery=0.08,
            currency="EUR",
        )

        assert settings.is_configured is True

    def test_price_settings_is_configured_false_no_currency(self):
        """Test is_configured returns False without currency."""
        settings = PriceSettings(consumption=0.30, delivery=0.08)

        assert settings.is_configured is False

    def test_price_settings_is_configured_false_no_prices(self):
        """Test is_configured returns False without prices."""
        settings = PriceSettings(currency="EUR")

        assert settings.is_configured is False

    def test_price_settings_is_consumption_configured(self):
        """Test is_consumption_configured property."""
        settings = PriceSettings(consumption=0.30, currency="EUR")

        assert settings.is_consumption_configured is True
        assert settings.is_delivery_configured is False

    def test_price_settings_is_delivery_configured(self):
        """Test is_delivery_configured property."""
        settings = PriceSettings(delivery=0.08, currency="EUR")

        assert settings.is_delivery_configured is True
        assert settings.is_consumption_configured is False

    def test_price_settings_price_in_with_consumption(self):
        """Test price_in returns consumption price."""
        settings = PriceSettings(consumption=0.30)

        assert settings.price_in == pytest.approx(0.30)

    def test_price_settings_price_in_without_consumption(self):
        """Test price_in returns 0.0 when consumption not set."""
        settings = PriceSettings()

        assert settings.price_in == pytest.approx(0.0)

    def test_price_settings_price_out_with_delivery(self):
        """Test price_out returns delivery price."""
        settings = PriceSettings(delivery=0.08)

        assert settings.price_out == pytest.approx(0.08)

    def test_price_settings_price_out_without_delivery(self):
        """Test price_out returns 0.0 when delivery not set."""
        settings = PriceSettings()

        assert settings.price_out == pytest.approx(0.0)


class TestEnergySettings:
    """Tests for EnergySettings class."""

    def test_energy_settings_defaults(self):
        """Test EnergySettings default values."""
        settings = EnergySettings()

        assert settings.retain is False

    def test_energy_settings_custom_values(self):
        """Test EnergySettings with custom values."""
        settings = EnergySettings(retain=True)

        assert settings.retain is True
