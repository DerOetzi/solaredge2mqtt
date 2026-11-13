import pytest

from solaredge2mqtt.services.energy.prices import PriceResolver
from solaredge2mqtt.services.energy.settings import PriceSettings


class TestPriceResolver:
    def test_returns_the_flat_prices_at_any_time(self):
        resolver = PriceResolver(
            PriceSettings(consumption=0.30, delivery=0.08, currency="EUR")
        )

        assert resolver.consumption_at(0) == pytest.approx(0.30)
        assert resolver.delivery_at(1_800_000_000) == pytest.approx(0.08)

    def test_unset_prices_resolve_to_zero(self):
        resolver = PriceResolver(PriceSettings())

        assert resolver.consumption_at(0) == pytest.approx(0.0)
        assert resolver.delivery_at(0) == pytest.approx(0.0)

    def test_is_configured_follows_the_settings(self):
        assert PriceResolver(
            PriceSettings(consumption=0.30, currency="EUR")
        ).is_configured
        assert not PriceResolver(PriceSettings(consumption=0.30)).is_configured
