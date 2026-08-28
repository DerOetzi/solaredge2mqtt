# 0006 — A local SQLite file replaces InfluxDB

**Status:** Accepted
**Context:** InfluxDB was a mandatory external service for everything beyond plain MQTT publishing: without it there is no `EnergyService` (the "today / this year / lifetime" sensors) and no `ForecastService` (pvlearn training data). `influxdb-client` was even a hard runtime dependency although the feature itself was optional.

## Decision 1: an embedded SQLite file, not another server

**Decision:** All time series move into `<config_dir>/solaredge2mqtt.db`, opened through `aiosqlite` in WAL mode. `solaredge2mqtt/core/influxdb/` including its Flux scripts is deleted and `influxdb-client` is dropped from the dependencies.

**Context:** The alternatives that keep the aggregation semantics all reintroduce the dependency that was to be removed: Postgres/TimescaleDB, QuestDB, VictoriaMetrics and InfluxDB 3 Core are servers, and delegating the history to Home Assistant's long-term statistics makes Home Assistant mandatory and keeps five-minute resolution for ten days only. DuckDB is embedded but holds a single-process file lock, so no second reader can attach while the service writes. Flat Parquet/CSV files have no safe concurrent append and would turn retention and the period queries into hand-written file surgery.

SQLite is the only candidate without a separate process that still tolerates a foreign reader, and the data volume is small: raw samples reach a steady state around 15 MB, the hourly aggregates grow by roughly 35 MB per year.

**Consequence:** `/app/config` is already the declared Docker volume, owned by uid 1000, and `sqlite3` ships with the base image — no Dockerfile change is needed and no apt package should be added. Grafana needs the community `frser-sqlite-datasource` plugin. A WAL database cannot be opened through a read-only bind mount, because SQLite has to create the `-shm` and `-wal` sidecar files; a Grafana container must mount the config directory read-write or use `?immutable=1`.

## Decision 2: a long table that mirrors the line protocol

**Decision:** `series(measurement, field, tags)` plus `point(series_id, ts, value)` declared `WITHOUT ROWID` with the primary key `(series_id, ts)`. Tags live in `series_tag`, keyed by series. The `value` column is declared without a type.

**Context:** The Flux code addressed the data as measurement/field/tag/value throughout, so a long table is a one-to-one translation and the InfluxDB import becomes a straight copy. `WITHOUT ROWID` with that primary key clusters every series contiguously and, through `ON CONFLICT DO UPDATE`, reproduces InfluxDB's "same series and timestamp overwrites" rule — which is exactly what the idempotent re-aggregation of the last hours relies on. A typeless column keeps SQLite's per-value affinity, so `forecast_training.weather_main` can stay a string next to the numeric fields, as it was in InfluxDB.

**Consequence:** No global index on `ts`: every query resolves its series first, and an additional index would double the write amplification at a five-second cadence for no benefit. Timestamps are integer seconds instead of InfluxDB's nanoseconds, which the five-second cadence and hourly aggregates never needed.

## Decision 3: period boundaries are computed in Python, aggregation buckets stay UTC

**Decision:** `core/storage/periods.py` computes the ten `HistoricPeriod` boundaries with `zoneinfo`, on naive wall-clock arithmetic, and passes unix timestamps as bound parameters. The hourly aggregation buckets by `(ts / 3600) * 3600`.

**Context:** SQLite's date functions cannot express "start of this month in the local zone, DST-aware"; `strftime(..., 'localtime')` follows the process `TZ` and silently drifts across a transition. Flux solved this with `option location` and `experimental/date/boundaries`, so the equivalent has to live somewhere — Python's `zoneinfo` is the only place in this stack that has the rules. The aggregation itself needs no zone: `aggregate.flux` set no `option location` either, so its windows were UTC hours.

**Consequence:** Calendar arithmetic must run on naive local wall-clock and attach the zone afterwards. Adding a `timedelta` to an aware datetime would add exactly 24 hours and be wrong twice a year. `periods.py` is pure and is tested against both hemispheres.

## Decision 4: breaking changes are taken openly, with an upgrade path

**Decision:** The configuration key becomes `storage:`, the MQTT status topic becomes `status/storage`, and the bucket retention becomes `retention_months`, defaulting to `0`, meaning "keep forever". A versioned configuration upgrade rewrites an existing `influxdb:` block, and `solaredge2mqtt-migrate-influxdb` copies the existing history into the new file.

**Context:** Pydantic ignores unknown keys, so an untouched `influxdb:` block would be dropped silently and users would lose a tuned `retention_raw` without noticing. The two-year retention was a property of the InfluxDB bucket, not a wish: locally there is little reason to discard hourly history that grows by 35 MB per year, and discarding it makes the lifetime totals lie.

**Consequence:** The upgrade backs the file up before rewriting it and records `config_version`. `influxdb_token` in `secrets.yml` is left in place — it may be referenced elsewhere — and only disappears from the example file.
