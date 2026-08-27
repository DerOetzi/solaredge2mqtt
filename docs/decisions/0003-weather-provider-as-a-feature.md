# 0003 — The weather provider is stamped onto every row

**Status:** Accepted — Decision 1 superseded by [ADR 0007](0007-storage-holds-the-canonical-schema.md)
**Context:** pvlearn 0.4.0 removed `ForecasterConfig.weather_provider` and turned `weather_provider` into a categorical feature of `pvlearn.schema`. Which provider a row came from is a per-row fact of the training data, not a training-run setting, so the library expects the adapter to supply it with the data. The same release also dropped `feature_schema_version`, `pipeline_version` and `sklearn_version` from the model sidecar in favour of the pvlearn release segment ([pvlearn ADR 0003](https://github.com/LearningHouseService/pvlearn/blob/main/docs/adr/0003-one-version-decides-model-compatibility.md)).

## Decision 1: the adapter stamps its own name, InfluxDB stores nothing

**Decision:** `OpenWeatherMapBaseData.PROVIDER_NAME` is written into every row by `to_canonical()` and `to_canonical_frame()`, on the way to the model. The `forecast_training` measurement gains no `weather_provider` field.

**Context:** Every stored snapshot was written by this adapter, so the provider of a row is derivable from where the row comes from, not something that has to be read back. Following [ADR 0002, Decision 1](0002-canonical-weather-schema.md), the measurement holds what the provider delivered; the provider's own name is not part of that payload.

**Consequence:** The constant lives on the weather model next to the mapping table rather than in `forecast/service.py`, where `WEATHER_PROVIDER` used to sit: a second provider brings its own name along with its own mapping, and no code in the forecast service has to know which one produced a row. Rows stored before this change get the same stamp on read, which is correct — OpenWeatherMap wrote them.

## Decision 2: nothing has to migrate for a pvlearn release

**Decision:** No compatibility handling for the changed feature set. `ForecastService` never calls `Forecaster.save()` or `load()`: the model lives in memory and is trained from `forecast_training` on the first prediction after a start.

**Context:** pvlearn's model sidecar and its version check exist for callers that persist a model across upgrades. A model trained on a different feature vocabulary keeps predicting plausible numbers, which is why loading one is a hard error there — a situation this service never reaches.

**Consequence:** A pvlearn bump costs one retrain, on a path the service already takes at every start. The stored `forecast_training` history is untouched and remains that retrain's input. Persisting the model later means honouring the sidecar's `SchemaMismatchError` and retraining on it, not defeating the check.
