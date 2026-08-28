# Legacy examples

These files belong to releases before 3.0.0, which stored the history in InfluxDB.

- `grafana_dashboard_influxdb.json` — the original dashboard, written entirely in Flux. It no
  longer works against the local SQLite database. It is kept as a reference for porting the
  remaining panels; `examples/grafana_dashboard_sqlite.json` covers the headline panels in SQL.

See [ADR 0006](../../docs/decisions/0006-sqlite-storage-instead-of-influxdb.md) for why InfluxDB
was replaced, and [the migration guide](../../docs/migration/influxdb-to-sqlite.md) for importing
an existing history.
