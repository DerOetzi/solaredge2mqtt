# Grafana and the Full Stack

Grafana reads the same SQLite database the service writes, through the community
`frser-sqlite-datasource` plugin. No exporter and no separate time-series service sit in
between.

## The stack

`examples/docker-compose-full-stack.yaml` runs the service, Grafana, and the image renderer that
Grafana needs for rendered panels:

```yaml
--8<-- "examples/docker-compose-full-stack.yaml"
```

The accompanying `examples/grafana.ini` sets the server URL for the container network and allows
anonymous read access:

```ini
--8<-- "examples/grafana.ini"
```

Download both next to your `config/` directory:

```bash
curl -o docker-compose.yml \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/examples/docker-compose-full-stack.yaml
curl -o grafana.ini \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/examples/grafana.ini

docker compose up -d
```

Grafana is then on port 3000.

!!! note "The database mount is read-write on purpose"

    SQLite runs in write-ahead-log mode and has to create the `-wal` and `-shm` sidecar files. A
    read-only mount of such a database cannot be opened at all, so Grafana gets the configuration
    directory read-write.

## Wiring up the datasource

1. In Grafana, add a datasource of type **SQLite**. The plugin is installed by the
   `GF_INSTALL_PLUGINS` variable in the compose file.
2. Set the path to `/app/config/solaredge2mqtt.db`.
3. Save and test.

Grafana runs as UID 1000 in this stack, matching the service, so it can open the file.

## The dashboard

[`examples/grafana_dashboard_sqlite.json`](https://github.com/DerOetzi/solaredge2mqtt/blob/main/examples/grafana_dashboard_sqlite.json)
covers the headline panels in SQL. Import it through **Dashboards, New, Import**.

The older Flux dashboard for InfluxDB is kept in
[`examples/legacy/`](https://github.com/DerOetzi/solaredge2mqtt/tree/main/examples/legacy) as a
reference for porting the remaining panels. It does not work against SQLite.

## Without containers

Nothing about this is Docker specific. Point any Grafana installation with the
`frser-sqlite-datasource` plugin at the database file, and give the Grafana user read and write
access to the directory holding it.
