from __future__ import annotations

from solaredge2mqtt.core.settings.loader import ConfigurationLoader
from solaredge2mqtt.core.settings.models import ServiceSettings


def service_settings(config_dir: str = "config") -> ServiceSettings:
    return ConfigurationLoader.load_configuration(config_dir)
