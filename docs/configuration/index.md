# Configuration Reference

Every option lives in `configuration.yml`, with sensitive values referenced out into
`secrets.yml`. If you have not created those files yet, start with
[First Configuration](../getting-started/configuration.md).

## Sections

| Section | Page | Purpose |
|---|---|---|
| `modbus` | [Modbus](modbus.md) | The inverter connection, meters, batteries, followers |
| `modbus.storedge_control_enabled` | [StorEdge Control](storedge-control.md) | Reading and writing the battery control block |
| `mqtt` | [MQTT](mqtt.md) | Broker, TLS, operational topics, retained messages |
| `monitoring` | [Monitoring](monitoring.md) | Module-level data and EV chargers from the SolarEdge site |
| `wallbox` | [Wallbox](wallbox.md) | SolarEdge Wallbox over its REST API |
| `homeassistant` | [Home Assistant](home-assistant.md) | Auto discovery |
| `storage` | [Storage](storage.md) | The local SQLite history and its retention |
| `prices` | [Prices](prices.md) | Savings and earnings from energy prices |
| `weather` | [Weather](weather.md) | OpenWeatherMap |
| `forecast` | [Forecast](forecast.md) | PV production forecasting |

## How to read the examples

Every page follows the same convention:

- An **uncommented** line is one you have to set yourself. Either the service refuses to start
  without it, or the feature stays switched off until it is there.
- A **commented** line is optional, and the value shown is the default that applies when you
  leave it out.

So the shortest working configuration is every uncommented line and nothing else.

## Basic settings

These sit at the top level of `configuration.yml`.

```yaml
# Optional, defaults shown
# interval: 5          # Seconds between data retrieval requests
# logging_level: INFO  # DEBUG, INFO, WARNING, ERROR or CRITICAL
```

`interval` drives everything: the Modbus poll, the monitoring poll, and the rate at which raw
samples are written to storage.

### Location

Required once you enable [weather](weather.md) or [forecast](forecast.md), and ignored
otherwise. There is no default.

```yaml
location:
  latitude: 52.520008
  longitude: 13.404954
```

### Powerflow

```yaml
# Optional, defaults shown
# powerflow:
#   external_production: false  # Set to true if you have producers the inverter cannot see
#   retain: false             # Keep the last power flow payload on the broker
```

### Energy

```yaml
# Optional, defaults shown
# energy:
#   retain: false  # Keep the last energy payload on the broker
```

## The packaged example

The file the service copies in on first start is kept in the repository and is the most
reliable listing of what exists:

- [`configuration.yml.example`](https://github.com/DerOetzi/solaredge2mqtt/blob/main/solaredge2mqtt/config/configuration.yml.example)
- [`secrets.yml.example`](https://github.com/DerOetzi/solaredge2mqtt/blob/main/solaredge2mqtt/config/secrets.yml.example)
