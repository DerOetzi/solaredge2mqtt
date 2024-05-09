from __future__ import annotations

from functools import lru_cache

from solaredge2mqtt.core.settings.models import ServiceSettings


@lru_cache()
def service_settings() -> ServiceSettings:
    return ServiceSettings()
