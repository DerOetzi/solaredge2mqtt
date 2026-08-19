# 0008 — The weather service hands out canonical snapshots

**Status:** Accepted
**Extends:** [ADR 0007](0007-storage-holds-the-canonical-schema.md)
**Context:** ADR 0007 moved the canonical schema into the storage, but the translation still happened at the last possible moment: `WeatherUpdateEvent` carried an `OpenWeatherMapOneCall`, so the forecast service was typed on the provider's model and called `model_dump_canonical()` on it. Adding a second provider would have meant teaching the forecast service about a second model.

## Decision 1: the event carries a provider independent result

**Decision:** `WeatherUpdateEvent` carries a `WeatherResult` (`services/weather/result.py`) holding `WeatherSnapshot` objects whose fields are `pvlearn.schema` — `temperature`, `cloud_cover`, `condition_code`, `wind_direction` and the rest, plus the `weather_provider` that produced them. `OpenWeatherMapOneCall.to_result()` and `OpenWeatherMapBaseData.to_snapshot()` do the translation inside the adapter.

**Context:** The translation belongs where the provider knowledge already is. Doing it at the edge means everything behind the weather service — the forecast service, the training data, the published payload — speaks one vocabulary, and a second provider is a second adapter with its own `CANONICAL_FIELDS`, not a change to any consumer.

**Consequence:** `services/forecast/service.py` no longer imports anything from `services/weather/models.py`; it is typed on `WeatherSnapshot`. `WeatherSnapshot` carries the `localtime`, `year`, `month`, `day` and `hour` helpers the forecast service buckets by, moved off the OpenWeatherMap model. The provider specific envelope of the One Call answer — coordinates, timezone offset — stops at the adapter. `OpenWeatherMapBaseData.to_canonical_field` stays, because the InfluxDB migration still needs the field mapping to convert stored history.

## Decision 2: the published weather payload is canonical too

**Decision:** `weather/current` publishes the canonical `WeatherSnapshot` instead of OpenWeatherMap's `current` object.

**Context:** Keeping the provider's shape on MQTT would have meant carrying the raw answer alongside the translated one purely for publishing, and would have left users with a payload that changes shape the day a second provider is configured.

**Consequence:** A breaking change to the payload: `temp` becomes `temperature`, `clouds` becomes `cloud_cover`, `weather_id` becomes the WMO `condition_code`, `weather_main` is gone, and every message names its `weather_provider`. Home Assistant discovery does not cover this topic, so no entity definitions break; automations reading the old field names have to be adjusted.
