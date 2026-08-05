"""Turns stored weather history into what the forecaster expects to be fed.

Snapshots are persisted under OpenWeatherMap's own field names (see
`services/weather/canonical.py`), so the translation to pvlearn's canonical
schema happens on the way out of InfluxDB. See
`docs/decisions/0002-canonical-weather-schema.md`.
"""

from __future__ import annotations

from typing import cast

from pandas import DataFrame

from solaredge2mqtt.services.weather.canonical import (
    OPENWEATHERMAP_TO_CANONICAL,
    to_wmo_code,
)

CONDITION_FIELD = "weather_id"


def to_canonical_frame(data: DataFrame) -> DataFrame:
    """Rename a `forecast_training` frame onto the canonical schema.

    Columns without a canonical counterpart are dropped, except `time` and the
    `energy` target, which the forecaster needs under those exact names. Rows
    older than a field's introduction simply carry NaN, which the forecaster
    tolerates.
    """
    canonical = data.copy()

    if CONDITION_FIELD in canonical.columns:
        canonical[CONDITION_FIELD] = canonical[CONDITION_FIELD].map(to_wmo_code)

    keep = {**OPENWEATHERMAP_TO_CANONICAL, "time": "time", "energy": "energy"}
    canonical = cast(
        DataFrame, canonical[[col for col in canonical.columns if col in keep]]
    )
    canonical.columns = [keep[str(col)] for col in canonical.columns]

    return canonical
