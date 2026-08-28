# SolarEdge2MQTT

SolarEdge2MQTT reads power data from a SolarEdge inverter over Modbus TCP and publishes it to an
MQTT broker. It is built for home automation: real-time power flow, battery state, grid import and
export, and meter readings, all as MQTT topics that Home Assistant can discover on its own.

Beyond the inverter itself, the service can log in to your SolarEdge monitoring account to read
module-level production and control an EV charger, keep a local history in a SQLite file, and
forecast tomorrow's production from that history and live weather data.

## What it does

- **Modbus communication** with SolarEdge inverters over TCP, including leader and follower
  setups with up to eleven inverters.
- **Power flow monitoring**: inverter production, battery charge and discharge, grid import and
  export, consumption and generation from the Modbus meters.
- **StorEdge battery control**: read and write the storage control block, including remote
  control of charge and discharge limits.
- **MQTT integration** with optional TLS, and **Home Assistant auto discovery**.
- **Local history** in a SQLite database. No external time-series service is required.
- **PV production forecasting** from a machine learning model, fed by the local history and
  OpenWeatherMap.
- **Price-based savings** for consumption and export.
- **SolarEdge Wallbox monitoring** over its REST API.
- **Module-level monitoring** through the SolarEdge monitoring site, without an API key.
- **Docker and Docker Compose** images for `linux/amd64` and `linux/arm64`.

## Where to start

<div class="grid cards" markdown>

- **New here?**

    Install the service and write your first configuration.

    [Installation](getting-started/installation.md)

- **Setting up a feature?**

    Every option, one page per service.

    [Configuration reference](configuration/index.md)

- **Running it in a container?**

    Docker, Compose, and the full stack with Grafana.

    [Deployment](deployment/docker.md)

- **Upgrading to 3.0.0?**

    Moving an InfluxDB history into the local storage.

    [Migration](migration/influxdb-to-sqlite.md)

</div>

## Getting help

- Ask on [Discord](https://discord.gg/QXfghc93pY).
- Report a problem or suggest something as a
  [GitHub issue](https://github.com/DerOetzi/solaredge2mqtt/issues).
- Check [Troubleshooting](troubleshooting.md) first for known symptoms.

If you find the project useful, a small
[contribution](https://www.buymeacoffee.com/deroetzik) is appreciated.
