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
#   retention_months: 0            # Months to keep everything, 0 keeps it forever
#   daily_backups: true            # Set to false to run without automatic backups
#   keep_backups: 7                # Backups to keep, 0 keeps every one
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
35 MB per year and is kept indefinitely unless you set `retention_months`.

`retention_months` counts whole calendar months back from the start of the current month, so
`24` keeps the last two years plus the months already elapsed this year. The pass runs once a
day and reclaims the freed pages afterwards.

## Backups

The service backs its database up once a day on its own, so a corrupted file or a deleted
container never costs more than a day of history. The backups land next to the database and are
rotated after `keep_backups` of them, seven by default. Set `daily_backups: false` to switch
the whole thing off, or `keep_backups: 0` to keep every backup forever.

Since the pass rides along with the ten minute aggregation, the first backup is written shortly
after the service starts and the following ones roughly 24 hours apart. A backup that fails, for
example because the filesystem is full, is logged and retried on the next pass. It never takes
the storage offline.

### Taking one by hand

`backup-database.sh` writes a consistent copy while the service keeps running. The Docker image
ships it on the `PATH`:

```bash
docker exec solaredge2mqtt backup-database.sh
```

From a source checkout it runs in the repository root:

```bash
scripts/backup-database.sh
```

Either way the copy lands next to the database as
`solaredge2mqtt.db.backup.<YYYYmmddHHMMSS>`, owned by the same user and with the same `0600`
mode as the original. The timestamp is UTC, exactly like the one the service stamps on its own
backups, so both end up in the same rotation.

| Option | Effect |
|---|---|
| `-c`, `--config-dir PATH` | Configuration directory to look in. Defaults to `./config`, then `/app/config` |
| `-d`, `--database PATH` | Database file, overrides `--config-dir` |
| `-k`, `--keep N` | Delete all but the `N` newest backups afterwards. Keeps every backup by default |

Do not copy the file with `cp` while the service holds it open. The database runs in
write-ahead-log mode, so a plain copy can miss the `-wal` sidecar and produce an inconsistent
snapshot. The script goes through SQLite instead: `VACUUM INTO` writes a compacted single file
without sidecars, and where the `sqlite3` command is missing it falls back to the backup API of
the Python standard library.

### Restoring one

Stop the service first, then put the backup in place:

```bash
mv config/solaredge2mqtt.db.backup.20260828152729 config/solaredge2mqtt.db
rm -f config/solaredge2mqtt.db-wal config/solaredge2mqtt.db-shm
```

The sidecars of the replaced database belong to a different file. Left behind, they would make
SQLite replay a foreign write-ahead log.

## Reading it from Grafana

Grafana talks to the file through the community `frser-sqlite-datasource` plugin. See
[Grafana](../deployment/grafana.md) for a working stack.

## Coming from InfluxDB

Releases before 3.0.0 kept the history in InfluxDB. Importing it is a one-off step described in
[Migrating from InfluxDB to SQLite](../migration/influxdb-to-sqlite.md).

Background on why the change was made is in
[decision 0006](../decisions/0006-sqlite-storage-instead-of-influxdb.md).
