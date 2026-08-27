# 0007 — The storage holds pvlearn's canonical schema

**Status:** Accepted
**Supersedes:** [ADR 0002](0002-canonical-weather-schema.md) Decision 1 and [ADR 0003](0003-weather-provider-as-a-feature.md) Decision 1
**Context:** [ADR 0006](0006-sqlite-storage-instead-of-influxdb.md) replaces InfluxDB with a local SQLite database, so the stored history is rewritten once anyway. The two earlier decisions — keep the provider's own field names in `forecast_training`, and stamp the provider name on every read instead of storing it — were made under the constraint that the existing measurement could not be touched. That constraint is gone.

## Decision 1: the measurement stores canonical field names, not the provider's

**Decision:** `forecast_training` stores `temperature`, `cloud_cover`, `condition_code` and the rest of `pvlearn.schema`, written by `model_dump_canonical()`. The migration converts the imported InfluxDB history once, in `migrate_influxdb.training_point_to_canonical`. `OpenWeatherMapBaseData.to_canonical_frame` is gone; reading only selects the columns pvlearn knows (`ForecastService.frame_for_pvlearn`).

**Context:** The prediction path already spoke the canonical schema (`_prepare_estimation_data` calls `model_dump_canonical`), while the training path stored provider names and renamed them on every single read. One schema on both sides removes that asymmetry, and it removes the provider-specific frame conversion from the read path — which is what a second provider would otherwise have to be dispatched through, per row.

**Consequence:** The OpenWeatherMap condition id is translated to its WMO code at write time, so the translation is now permanent: correcting `CONDITION_TO_WMO` later no longer changes historic rows, they would need a second migration. Fields without a canonical counterpart are not stored any more — `weather_main` is dropped by the migration, `snow` is not written. `energy` and `power` keep their own names next to the features. `tests/test_pvlearn_wiring_regression.py` puts the pre-migration reference export through the same conversion and still reproduces the frozen MAE and R², so the switch costs no predictive quality.

## Decision 2: the provider is a stored field, not a tag and not a read-time stamp

**Decision:** `weather_provider` is written into every `forecast_training` snapshot as an ordinary field, and read back from there. The migration stamps `openweathermap` onto every imported row.

**Context:** pvlearn treats `weather_provider` as a per-row categorical feature (`pvlearn.schema.CATEGORICAL_FEATURES`), so it has to arrive as a column. Storing it as a tag of the series was considered: two providers writing the same hour would then land in separate series instead of overwriting each other on the `(series_id, ts)` primary key. It was rejected because that collision can only happen in the single hour a switch falls into, while a tag would have to be folded back into a column on every read — the exact conversion this ADR removes.

**Consequence:** The history stays usable across a provider switch instead of forcing a retrain: the model simply sees a new category value, which is what the schema's own documentation describes. `OpenWeatherMapBaseData.PROVIDER_NAME` is still the single place the adapter's name is written, now used by the write path and by the migration rather than by every read. A second adapter brings its own name and its own `CANONICAL_FIELDS`, and needs no change on the read path at all.
