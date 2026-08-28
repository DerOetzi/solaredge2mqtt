# Migrating from InfluxDB to SQLite

!!! info "Affects the upgrade to 3.0.0"

    Relevant when you upgrade from a release **before 3.0.0** whose `configuration.yml` has an
    `influxdb` section. A fresh installation of 3.0.0 or later writes to SQLite from the start and
    can skip this page.

    Upgrading from before 2.3.0 means going through
    [the environment variable migration](environment-variables.md) as well.

Up to 3.0.0 the history lived in an InfluxDB bucket, which had to be installed, configured and
kept running alongside the service. It now lives in a SQLite file inside the configuration
directory, with no external service at all. The reasoning is in
[decision 0006](../decisions/0006-sqlite-storage-instead-of-influxdb.md).

This guide covers the upgrade: what happens on its own, and how to bring your existing history
across.

## What happens on the first start

Nothing is required of you up front. On the first start of 3.0.0 the service upgrades
`configuration.yml` by itself:

1. It writes a timestamped backup next to the file,
   `configuration.yml.backup.<timestamp>`.
2. It logs the exact import command for your InfluxDB, filled in with the host, organization and
   bucket it is about to remove.
3. It removes the `influxdb` section and replaces it with a `storage` section, carrying over
   `retention_raw` and `debounce_cycles` if they were set.
4. It stamps `config_version: 1` into the file so the upgrade does not run twice.

From then on the service records into SQLite. **Your InfluxDB history is not touched, and not
imported.** Importing it is the separate step below.

!!! warning "Copy the command out of the log"

    The `influxdb` section is the only place the host, organization and bucket are written down,
    and the upgrade removes it. That is why the command is logged before the rewrite. If you
    missed it, the values are still in the `configuration.yml.backup.*` file.

The rewritten file is generated YAML. Comments and formatting from your original are not
preserved, which is what the backup is for.

## Importing the history

The `solaredge2mqtt-migrate-influxdb` command reads an InfluxDB 2.x bucket and writes it into the
storage database. It is idempotent, so a repeated or interrupted run is safe.

=== "Before the first start"

    While the `influxdb` section is still in `configuration.yml`, the command reads the
    connection from there. Nothing else is needed:

    ```bash
    solaredge2mqtt-migrate-influxdb --config-dir config
    ```

=== "After the upgrade"

    The section is gone, so pass the connection explicitly. This is the command the upgrade
    logged:

    ```bash
    solaredge2mqtt-migrate-influxdb --config-dir config \
        --url http://influxdb:8086 \
        --org my_org \
        --bucket solaredge \
        --token YOUR_INFLUXDB_TOKEN
    ```

    Substitute the `influxdb_token` entry from `secrets.yml`, which the upgrade leaves alone.

=== "From a dump"

    No running InfluxDB is needed if you have a line protocol export:

    ```bash
    influx query --raw '...' > influx-export.lp   # or influxd inspect export-lp

    solaredge2mqtt-migrate-influxdb --from-lp ./influx-export.lp
    ```

!!! note "The token is never logged"

    The logged command carries the placeholder `YOUR_INFLUXDB_TOKEN`, never the real value. A
    token in the service log is a token in journald, in the Docker logs, and in every log
    somebody attaches to an issue.

### In a container

```bash
docker compose run --rm solaredge2mqtt \
    solaredge2mqtt-migrate-influxdb --config-dir /app/config \
    --url http://influxdb:8086 --org my_org --bucket solaredge --token YOUR_INFLUXDB_TOKEN
```

The InfluxDB container has to be reachable from that network while the import runs.

## Command options

| Option | Default | Meaning |
|---|---|---|
| `--config-dir` | `config` | Where `configuration.yml` and the database live |
| `--url` | from the old section | InfluxDB base URL. A bare host gets `https://` and port 8086 |
| `--org` | from the old section | InfluxDB organization |
| `--bucket` | `solaredge` | Bucket to read |
| `--token` | from `secrets.yml` | InfluxDB API token |
| `--from-lp` | none | Read a line protocol dump instead of querying a server |
| `--start` | 1970-01-01 | ISO timestamp, earliest point to import |
| `--stop` | now | ISO timestamp, latest point to import |
| `--measurements` | see below | Comma separated list, overrides the default selection |
| `--include-raw` | off | Also import `powerflow_raw` and `battery_raw` |
| `--slice-days` | `1` | Days queried per request. Lower it if InfluxDB times out |
| `--dry-run` | off | Read and report without writing |
| `--resume` | off | Continue after the newest point already in storage |

Without `--measurements`, six series are imported: `energy`, `powerflow`, `battery`,
`forecast_training`, `forecast` and `modules`.

Raw samples are skipped by default. They expire within a day anyway, so importing years of them
costs time and space for data the service is about to delete. Add `--include-raw` if you want
them regardless.

## Suggested order

1. **Dry run first.** `--dry-run` reports what would be written without touching the database.
2. **Import.** Expect it to take a while on a multi-year bucket. `--slice-days` controls the
   query size if InfluxDB struggles.
3. **Check the result.** The command logs `Import finished, N rows written`.
4. **Repeat if it broke off.** The import is idempotent. `--resume` skips ahead to what is
   already stored instead of rechecking everything.
5. **Clean up.** Remove `influxdb_token` from `secrets.yml`, then stop and remove the InfluxDB
   container or service.

## Two conversions happen during the import

These are not optional and run as part of every import.

### Weather fields are converted

The forecast training history is rewritten onto the schema the forecast model speaks. `temp`
becomes `temperature`, the OpenWeatherMap condition id becomes its WMO code, the provider is
stamped into every row, and fields the model has no use for, such as `weather_main`, are dropped.

See [decision 0007](../decisions/0007-storage-holds-the-canonical-schema.md).

### Module series are merged

The monitoring API changed what it reports as an optimizer's identifier, so an older history
holds the same physical module under several tag sets. The import folds them onto the shape
written today, keyed by the serial number, and drops the merged series.

A dashboard that pinned the numeric optimizer id has to be repointed at the serial number. See
[decision 0009](../decisions/0009-migration-consolidates-the-module-series.md).

## Afterwards

- Point Grafana at the SQLite file, see [Grafana](../deployment/grafana.md). The old Flux
  dashboard does not work against SQLite and is kept only as a porting reference.
- Review the [storage settings](../configuration/storage.md), in particular `retention_raw` and
  `retention_months`.
- Remove `influxdb_token` from `secrets.yml`. The service no longer reads it.
