"""Tests for powerflow settings module."""


from solaredge2mqtt.services.powerflow.settings import PowerflowSettings


class TestPowerflowSettings:
    """Tests for PowerflowSettings class."""

    def test_powerflow_settings_defaults(self):
        """Test PowerflowSettings default values."""
        settings = PowerflowSettings()

        assert settings.external_production is False
        assert settings.retain is False

    def test_powerflow_settings_custom_values(self):
        """Test PowerflowSettings with custom values."""
        settings = PowerflowSettings(
            external_production=True,
            retain=True,
        )

        assert settings.external_production is True
        assert settings.retain is True

    def test_powerflow_settings_external_production_flag(self):
        """Test external_production flag."""
        settings_false = PowerflowSettings(external_production=False)
        settings_true = PowerflowSettings(external_production=True)

        assert settings_false.external_production is False
        assert settings_true.external_production is True

    def test_powerflow_settings_retain_flag(self):
        """Test retain flag."""
        settings_false = PowerflowSettings(retain=False)
        settings_true = PowerflowSettings(retain=True)

        assert settings_false.retain is False
        assert settings_true.retain is True
