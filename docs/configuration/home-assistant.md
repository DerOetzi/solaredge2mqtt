# Home Assistant Auto Discovery

Publishes discovery messages so Home Assistant creates the entities itself, with no manual YAML
on the Home Assistant side.

```yaml
homeassistant:
  enable: true                   # Off by default

  # Optional, defaults shown
  # topic_prefix: homeassistant  # MQTT discovery topic prefix
  # retain: false               # Keep the discovery messages on the broker
```

`topic_prefix` has to match Home Assistant's own discovery prefix, which is `homeassistant`
unless you changed it.

`retain` is worth turning on here. Retained discovery messages mean Home Assistant finds the
entities again after a restart without waiting for SolarEdge2MQTT to republish them. Note
that retained messages also have to be cleared from the broker when you remove entities.

## Removing the entities again

Order matters:

1. Set `enable: false`.
2. Restart SolarEdge2MQTT first.
3. Then restart Home Assistant.

Restarting them the other way round leaves the entities behind as unavailable.

## What gets created

Entities follow whatever else is enabled:

- The inverter, its meters and its batteries, from [Modbus](modbus.md).
- Select and number entities for the battery control block, when
  [StorEdge control](storedge-control.md) is on.
- Charge level, status, plug state, session energy and rated power per EV charger, when
  [monitoring](monitoring.md) is configured.
- The wallbox, when [that section](wallbox.md) is configured.

The `weather/current` topic is deliberately not covered by discovery.
