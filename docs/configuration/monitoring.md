# Monitoring

Reads module-level energy and power values from the SolarEdge monitoring platform. It uses your
normal platform account, not the official API, so no API key is required.

```yaml
monitoring:
  site_id: !secret monitoring_site_id    # Your SolarEdge site ID
  username: "user@example.com"           # SolarEdge platform username
  password: !secret monitoring_password  # Platform password

  # Optional, defaults shown
  # retain: false      # Keep the last module and EV charger payload on the broker
  # debounce_cycles: 2  # Failed polls before monitoring is reported offline
```

All three credentials are needed. With any of them missing the service stays switched off.

`debounce_cycles` guards against a single failed poll of the SolarEdge site marking the
service offline. The monitoring platform is reached over the internet, so a raised value
is worth having on a shaky connection.

```yaml
# secrets.yml
monitoring_site_id: "12345678"
monitoring_password: "your_monitoring_password"
```

Module data is written to the [storage](storage.md) as the `modules` series, keyed by the
optimizer serial number.

## EV charger monitoring and control

EV chargers registered in the same monitoring account are discovered automatically at startup.
Nothing beyond the credentials above is needed.

Status is polled on every base `interval` and published under:

```
monitoring/evcharger/{reporter_id}
```

The payload carries:

| Field | Description |
|---|---|
| `charge_level` | Current charge level, 0 to 100 percent |
| `charger_status` | Status string, for example `CHARGING` or `IDLE` |
| `connected` | Whether a vehicle is plugged in |
| `session_energy` | Energy delivered in the current session, in watt hours |
| `rated_power` | Rated charging power, in watts |

### Setting the charge level

Publish to:

```
monitoring/evcharger/{reporter_id}/charge_level
```

with:

```json
{"level": 100}
```

`level` must be `0` for off or `100` for on. Intermediate values are not currently possible. The
service translates this into a MANUAL mode command sent to the monitoring API.

### Home Assistant entities

With [auto discovery](home-assistant.md) enabled, each charger gets:

- a **number** entity for charge level control,
- a **sensor** for the charger status,
- a **binary sensor** for whether a vehicle is plugged in,
- and **sensors** for session energy and rated power.
