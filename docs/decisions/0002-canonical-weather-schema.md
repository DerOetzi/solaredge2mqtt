# 0002 — Speaking pvlearn's canonical weather schema

**Status:** Accepted — Decision 1 superseded by [ADR 0007](0007-storage-holds-the-canonical-schema.md)
**Context:** Phase 1b of [pvlearn's Umsetzungsplan](https://github.com/LearningHouseService/pvlearn/blob/main/pvlearn-umsetzungsplan.md) — pvlearn 0.2.0 dropped the power model, publishes energy in Wh and expects provider-independent feature names (chapter 3.1) instead of OpenWeatherMap's. Mapping onto them is the caller's job until the provider adapters arrive in Phase 2.

## Decision 1: InfluxDB keeps the provider's field names, the translation happens on read

**Decision:** Weather snapshots are still written to `forecast_training` under OpenWeatherMap's own field names (`clouds`, `temp`, `weather_id`, …). `OpenWeatherMapBaseData.to_canonical_frame()` renames them onto the canonical schema when the training data comes back out of InfluxDB, and `OpenWeatherMapBaseData.model_dump_canonical()` does the same for the live prediction input.

**Context:** The alternative — writing canonical names — would have made the stored history unreadable to the new code. Training needs a minimum of 60 hours of consistent data, so every subscriber would have lost their forecast for at least that long after the update, and the year of history that exists would have been dead weight.

**Consequence:** A schema change on pvlearn's side is a change to one mapping table, never a migration of the measurement. The price is that the stored data is only meaningful together with the mapping, so a second provider carries its own mapping on its own model rather than sharing one.

## Decision 2: `condition_code` is a WMO 4677 code, and the mapping is lossy on purpose

**Decision:** `OpenWeatherMapBaseData.CONDITION_TO_WMO` translates OpenWeatherMap's condition ids into WMO 4677 weather codes — the code space Open-Meteo and the DWD report in. Unknown ids become 3 (overcast), a missing id stays missing.

**Context:** The canonical schema needs one code space, otherwise a model trained here means nothing anywhere else. WMO is the one the other candidate providers already use, and OpenWeatherMap is the odd one out. The two do not line up: WMO knows four cloudiness steps against OpenWeatherMap's five, and distinguishes hail thunderstorms where OpenWeatherMap does not.

**Consequence:** Some nuance is lost in the translation. It costs little because the model is ultimately asking how much light reaches the panels, `cloud_cover` carries the cloudiness as a percentage anyway, and where WMO has no equivalent the nearest optically similar condition wins. Unknown ids default to overcast rather than clear because a code the table does not know is far more likely to be weather than a cloudless sky.

## Decision 3: the `forecast` measurement keeps its unit and its `power` field

**Decision:** pvlearn publishes Wh, but `_write_periods_to_influxdb` keeps storing `energy` in kWh and keeps writing `power` alongside it.

**Context:** Changing the unit of an existing field in place is silent: no query fails, every existing Grafana dashboard just shows numbers a thousand times larger, and any window spanning the update mixes both scales with nothing to tell them apart.

**Consequence:** The conversion lives at the two InfluxDB boundaries (`WH_PER_KWH` on write, and back on read in `publish_forecast`). `power` is measured data in `forecast_training` and stays recorded there too — dropping a field from the history cannot be undone, and it costs nothing to keep. It is written as an integer, the type the power model gave it: InfluxDB refuses a float onto an integer field and drops the whole batch with `field type conflict`.

## Decision 4: `power_period` stays in the MQTT payload as a derived shim

**Decision:** `Forecast.from_energy_period` fills `power_period` with a copy of `energy_period`. The field is deprecated and removed after at least two minor releases.

**Context:** pvlearn no longer predicts power at all: the power model trained on identical features and, at hourly resolution, produced the same number in a different unit (620.88 against 624.93 MAE on the reference dataset). Subscribers — including the [companion Home Assistant integration](https://github.com/DerOetzi/solaredge2mqtt_forecast) — read the field today, and dropping it in the same release that changes the model would break them without warning.

**Consequence:** The identity holds only because the interval is 60 minutes, which is why `INTERVAL_MINUTES` is named in `forecast/models.py` next to the shim and disappears together with it. At a finer resolution the mean power would be `energy * 60 / interval_minutes`, so the field has to be gone before a sub-hourly interval is offered.
