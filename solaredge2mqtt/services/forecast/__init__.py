from __future__ import annotations

import importlib.util

_FORECAST_DEPS = ("numpy", "pandas", "scipy", "sklearn")


def _deps_available() -> bool:
    return all(importlib.util.find_spec(pkg) is not None for pkg in _FORECAST_DEPS)


FORECAST_AVAILABLE: bool = _deps_available()


if FORECAST_AVAILABLE:
    from .service import ForecastService
    __all__ = ["ForecastService"]
else:
    class ForecastService:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                (
                    "ForecastService requires to install extra dependencies. "
                    "Run pip install solaredge2mqtt[forecast]"
                )
            )
