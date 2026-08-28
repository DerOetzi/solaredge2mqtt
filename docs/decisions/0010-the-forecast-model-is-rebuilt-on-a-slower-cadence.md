# 0010 — The forecast model is rebuilt on a slower cadence than its training data

**Status:** Accepted
**Extends:** [ADR 0001](0001-pvlearn-extraction-wiring.md)
**Context:** Every hour the weather update writes one row of training data, and until now the same trigger rebuilt the model from the full history at minute 20 — a complete fit over all stored hours, including the permutation-importance feature selection, and with `hyperparametertuning` enabled a `HalvingGridSearchCV` search on top. On an installation with a year of history that is 8760 rows refitted to absorb one new hour, on hardware that usually runs this service next to everything else in a home lab.

## Decision 1: the retraining interval follows the amount of training data

**Decision:** `ForecastService.scheduled_training()` still runs hourly, but only trains when the last successful run is at least one interval old. The interval comes from `training_interval_hours(rows)`: below 30 days of stored hours the model is rebuilt every hour as before, from 30 days on once a day. `forecast.training_interval_hours` overrides both with a fixed number of hours. `DUE_TOLERANCE` lets a run that is due a few minutes early still happen, because the trigger fires within a ten minute window and would otherwise skip a whole interval.

**Context:** A new hour has to compete with everything already stored. While the history is short it moves the model measurably, which is exactly the phase in which a fresh installation is still becoming useful, so nothing is throttled there. Once a month of history has accumulated, one hour is a fraction of a percent of the training set and the prediction it produces is indistinguishable from the previous one — the CPU time is spent regardless.

Two alternatives were rejected. A fixed interval as the only mechanism is simple but wrong at both ends: 24 hours starves a new installation, one hour never stops burning CPU on a mature one. Retraining when the new rows exceed a share of the training set is self-scaling but drifts into intervals nobody asked for — five percent of a year is eighteen days — and makes the next run impossible to predict from the configuration alone.

**Consequence:** A prediction can be based on a model up to a day old on a mature installation. The data it predicts from stays current, because the weather forecast is read on every ten minute loop and only the model behind it ages. A failed training run does not update the timestamp and is therefore retried on the next hour rather than skipped for a full interval.

## Decision 2: the hyperparameter search runs on its own, slower cadence

**Decision:** With `hyperparametertuning` enabled, a training run searches only when the last search is at least `hyperparametertuning_interval_days` old, seven by default; the runs in between fit with the parameters that search found. The timestamp is read from `Forecaster.hyperparameters_tuned_at` rather than from a counter in this service.

**Context:** The search dominates the runtime of a training run while its result is stable over weeks — the parameters describe how the plant behaves, not what the weather did yesterday. Splitting the two cadences only became possible with pvlearn 0.5.0, which keeps the found parameters across runs and takes a per-call `hyperparametertuning` argument ([pvlearn ADR 0004](https://github.com/LearningHouseService/pvlearn/blob/main/docs/adr/0004-hyperparameters-outlive-the-search.md)). Before that, a run without tuning silently reverted the model to the library defaults, which would have made every skipped search a downgrade rather than a saving.

Keeping the timestamp in the service was rejected once the model became persistent: the service's own counter would restart with the process and trigger a search for parameters the restored model already carries.

**Consequence:** Enabling `hyperparametertuning` no longer means paying for the search on every retraining. `hyperparametertuning_interval_days: 0` restores the old behaviour of tuning on every run.

## Decision 3: the trained model is persisted under the cache directory

**Decision:** After every successful training run the model is written to `<cachingdir>/model` via `Forecaster.save()`, and `ForecastService` loads it again on startup. A restored model seeds `last_training` from `ModelMetadata.trained_at`, so both cadences above survive a restart. Without a `cachingdir` there is no persistence.

**Context:** Without this, the throttling had a hole: a restart made the service retrain immediately and, with tuning enabled, search again — so a service that restarts daily never reaches the throttled state at all. The model lives in its own subdirectory because pvlearn trims its joblib cache below the same root to `cache_size_limit_mb`, and the model must not be part of what gets trimmed.

pvlearn refuses a persisted model whose metadata disagrees with the current setup, a new pvlearn release included ([pvlearn ADR 0003](https://github.com/LearningHouseService/pvlearn/blob/main/docs/adr/0003-one-version-decides-model-compatibility.md)). That refusal is treated as "train from scratch", not as an error: it is precisely the situation in which the old model must not be used.

**Consequence:** An update that ships a new pvlearn release costs one training run on the next trigger, which is the price of never predicting from a model whose feature set has moved. A model that cannot be written is logged and kept in memory, so a read-only cache directory degrades into the previous behaviour instead of failing the training run.
