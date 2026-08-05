"""Maps OpenWeatherMap's One Call fields onto pvlearn's canonical schema.

Translation only: persistence keeps the provider's own field names. See
`docs/decisions/0002-canonical-weather-schema.md`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: OpenWeatherMap One Call field -> canonical feature name. Fields with no
#: canonical counterpart are absent, and so are the canonical irradiance
#: features `ghi`, `dni` and `dhi`, which OpenWeatherMap does not deliver.
OPENWEATHERMAP_TO_CANONICAL: dict[str, str] = {
    "clouds": "cloud_cover",
    "temp": "temperature",
    "feels_like": "apparent_temperature",
    "dew_point": "dew_point",
    "humidity": "relative_humidity",
    "pressure": "surface_pressure",
    "rain": "precipitation",
    "pop": "precipitation_probability",
    "uvi": "uv_index",
    "visibility": "visibility",
    "wind_speed": "wind_speed",
    "wind_gust": "wind_gust",
    "wind_deg": "wind_direction",
    "weather_id": "condition_code",
}

#: OpenWeatherMap condition id -> WMO 4677 weather code, the code space the
#: canonical `condition_code` uses. Lossy in both directions; where WMO has no
#: equivalent, the nearest optically similar condition is used. See
#: `docs/decisions/0002-canonical-weather-schema.md`.
OPENWEATHERMAP_CONDITION_TO_WMO: dict[int, int] = {
    # Thunderstorm. WMO distinguishes hail (96, 99), OpenWeatherMap does not.
    200: 95,
    201: 95,
    202: 95,
    210: 95,
    211: 95,
    212: 95,
    221: 95,
    230: 95,
    231: 95,
    232: 95,
    # Drizzle.
    300: 51,
    301: 53,
    302: 55,
    310: 51,
    311: 53,
    312: 55,
    313: 81,
    314: 82,
    321: 80,
    # Rain.
    500: 61,
    501: 63,
    502: 65,
    503: 65,
    504: 65,
    511: 66,
    520: 80,
    521: 81,
    522: 82,
    531: 82,
    # Snow, including the mixed forms WMO files under showers.
    600: 71,
    601: 73,
    602: 75,
    611: 85,
    612: 85,
    613: 86,
    615: 71,
    616: 73,
    620: 85,
    621: 85,
    622: 86,
    # Atmosphere. Mist, smoke, haze, dust, sand and ash all scatter light the
    # way fog does, which is the only property that matters here.
    701: 45,
    711: 45,
    721: 45,
    731: 45,
    741: 45,
    751: 45,
    761: 45,
    762: 45,
    771: 80,
    781: 99,
    # Clear and clouds.
    800: 0,
    801: 1,
    802: 2,
    803: 3,
    804: 3,
}

#: What an unknown condition id becomes: overcast.
UNKNOWN_CONDITION_WMO_CODE = 3


def to_wmo_code(condition_id: int | float | None) -> int | None:
    """Translate one OpenWeatherMap condition id to its WMO code."""
    if condition_id is None:
        return None

    return OPENWEATHERMAP_CONDITION_TO_WMO.get(
        int(condition_id), UNKNOWN_CONDITION_WMO_CODE
    )


def to_canonical(estimation_data: Mapping[str, Any]) -> dict[str, Any]:
    """Rename one weather snapshot onto the canonical schema."""
    canonical: dict[str, Any] = {}

    for field, value in estimation_data.items():
        canonical_name = OPENWEATHERMAP_TO_CANONICAL.get(field)
        if canonical_name is None:
            continue

        if field == "weather_id":
            value = to_wmo_code(value if isinstance(value, (int, float)) else None)

        canonical[canonical_name] = value

    return canonical
