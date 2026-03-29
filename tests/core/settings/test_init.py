"""Tests for settings package helpers."""

from unittest.mock import patch

from solaredge2mqtt.core.settings import service_settings


class TestSettingsInit:
    """Tests for settings package entrypoints."""

    def test_service_settings_delegates_to_loader(self):
        """service_settings should delegate to ConfigurationLoader."""
        expected = object()

        with patch(
            "solaredge2mqtt.core.settings.ConfigurationLoader.load_configuration",
            return_value=expected,
        ) as mock_load:
            result = service_settings("custom-config")

        mock_load.assert_called_once_with("custom-config")
        assert result is expected
