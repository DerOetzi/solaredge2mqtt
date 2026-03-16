"""Tests for homeassistant settings module."""


from solaredge2mqtt.services.homeassistant.settings import HomeAssistantSettings


class TestHomeAssistantSettings:
    """Tests for HomeAssistantSettings class."""

    def test_homeassistant_settings_defaults(self):
        """Test HomeAssistantSettings default values."""
        settings = HomeAssistantSettings()

        assert settings.enable is False
        assert settings.topic_prefix == "homeassistant"
        assert settings.retain is False

    def test_homeassistant_settings_custom_values(self):
        """Test HomeAssistantSettings with custom values."""
        settings = HomeAssistantSettings(
            enable=True,
            topic_prefix="custom_ha",
            retain=True,
        )

        assert settings.enable is True
        assert settings.topic_prefix == "custom_ha"
        assert settings.retain is True

    def test_homeassistant_settings_topic_prefix_custom(self):
        """Test custom topic prefix."""
        settings = HomeAssistantSettings(topic_prefix="my_ha_prefix")

        assert settings.topic_prefix == "my_ha_prefix"
