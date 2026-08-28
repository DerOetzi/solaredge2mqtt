# Storage

The history lives in a SQLite database inside the configuration directory. It is enabled by
default and needs no external service.

The whole section is optional. Every field below has a working default, so leave it out
entirely unless you want to change something.

```yaml
# Optional, defaults shown
# storage:
#   enable: true                   # Set to false to run without any history
#   filename: solaredge2mqtt.db    # File name inside the configuration directory
#   path: /data/solaredge2mqtt.db  # Absolute path, overrides filename, no default
#   retention_raw: 25              # Hours to keep the raw samples
#   retention: 0                   # Seconds to keep everything, 0 keeps it forever
#   debounce_cycles: 2             # Failed writes before storage is reported offline
```

`debounce_cycles` sets how many consecutive failed writes it takes before storage is
published as offline. It has to be at least 1.

Storage is a prerequisite for [prices](prices.md) and [forecast](forecast.md). Both need the
history to compute anything.

## What is written, and when

Raw samples are written at the polling `interval`. Every ten minutes they are aggregated into
hourly minimum, maximum, mean and energy values.

Only the raw samples expire, after `retention_raw` hours. The hourly history grows by roughly
35 MB per year and is kept indefinitely unless you set `retention`.

## Backups

The database can be copied while the service is running:

```bash
sqlite3 config/solaredge2mqtt.db "VACUUM INTO 'solaredge2mqtt-backup.db'"
```

Do not copy the file with `cp` while the service holds it open. The database runs in
write-ahead-log mode, so a plain copy can miss the `-wal` sidecar and produce an inconsistent
snapshot.

## Reading it from Grafana

Grafana talks to the file through the community `frser-sqlite-datasource` plugin. See
[Grafana](../deployment/grafana.md) for a working stack.

## Coming from InfluxDB

Releases before 3.0.0 kept the history in InfluxDB. Importing it is a one-off step described in
[Migrating from InfluxDB to SQLite](../migration/influxdb-to-sqlite.md).

Background on why the change was made is in
[decision 0006](../decisions/0006-sqlite-storage-instead-of-influxdb.md).
