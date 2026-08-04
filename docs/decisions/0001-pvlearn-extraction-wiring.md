# 0001 — Wiring solaredge2mqtt to the pvlearn forecast core

**Status:** Accepted
**Context:** Phase 1a of [pvlearn's Umsetzungsplan](https://github.com/LearningHouseService/pvlearn/blob/main/pvlearn-umsetzungsplan.md) — `Forecaster`, `PFISelector`, `ForecasterType` and all encoders moved out of this repo into the standalone `pvlearn` package.

## Decision 1: regression test compares predictive quality, not exact predictions

**Decision:** `tests/test_pvlearn_wiring_regression.py` asserts the wired-up `ForecastService` reproduces the frozen Phase 0 baseline's MAE (within 10%) and R² (within 0.05), not bit-identical prediction values.

**Context:** The test originally asserted exact equality. It passed on every local run and failed in CI. Root cause, isolated by ruling out alternatives one at a time (thread count via `n_jobs`/`OMP_NUM_THREADS`, Python 3.12 vs 3.13 — none of these changed the result on the same machine): `HistGradientBoostingRegressor`'s greedy split search is sensitive to CPU-microarchitecture-dependent floating point rounding (SIMD reduction order). A razor-edge split threshold flips on different hardware, and the tree below it looks completely different, even with `random_state=42` fixed and identical library versions everywhere.

**Consequence:** Bit-identical reproducibility across arbitrary hardware isn't achievable with this pipeline. Any future regression test built on this dataset/model needs a tolerance-based comparison, not exact equality. The same finding and fix apply on the pvlearn side; see chapter 6 of its Umsetzungsplan and [pvlearn PR #10](https://github.com/LearningHouseService/pvlearn/pull/10).

## Decision 2: pvlearn's exceptions are translated back to InvalidDataException at the service boundary

**Decision:** `ForecastService.training()` and `.predict()` catch `pvlearn.exceptions.PVLearnError` and re-raise as `InvalidDataException(str(error))`.

**Context:** `Forecaster.train()`/`.predict()` used to raise this repo's own `InvalidDataException` directly, since `Forecaster` used to live here. Now it raises pvlearn's own `InsufficientDataError`/`ModelNotTrainedError`. The EventBus's listener error handling (`core/events/__init__.py::_notify_listener`) only catches `InvalidDataException` to log a warning and continue; anything else is logged as an unhandled listener error, which is a real (if non-fatal) behavior change.

**Consequence:** Translating at the two call sites keeps the EventBus's existing error handling untouched and behavior-identical, without teaching the EventBus about a third-party library's exception hierarchy.

## Decision 3: Forecast inherits pvlearn.ForecastResult, re-decorating each aggregation property

**Decision:** `Forecast(Component, ForecastResult)`. `pvlearn.ForecastResult` carries the energy aggregation logic (`energy_today`, `energy_today_remaining`, `energy_current_hour`, `energy_next_hour`, `energy_tomorrow`) as plain `@property`. `Forecast` redeclares each one as `@computed_field @property`, delegating to `super()`.

**Context:** pvlearn's version is intentionally decoration-free — it doesn't know about Home Assistant or `@computed_field`. Without redeclaring the properties in `Forecast`, the values would still be reachable via plain attribute access but would silently drop out of `model_dump()`/`model_dump_json()`, and therefore out of the MQTT/HA discovery payload.

**Consequence:** The aggregation logic exists exactly once (in pvlearn); the HA-specific decoration lives only in `Forecast`. Verified via `Forecast.model_dump()` including the fields and `Forecast.model_json_schema()` still excluding `energy_period`/`power_period` as before.
