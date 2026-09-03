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

## After upgrading: the EV charger session energy statistic

The EV charger's session energy is now published as `state_class: total_increasing` instead of
`measurement`, because it counts up during a session and resets to zero at the start of the next
one. Home Assistant stores a sum statistic for it from now on, where it used to store a
mean/min/max one.

For an existing installation that means one manual step, once the new discovery message has been
picked up:

1. Home Assistant raises a repair issue about the changed statistics for that entity.
2. Open Developer Tools → Statistics, find the entity, and delete its old statistics through the
   issue.

The sum statistic starts from the next update. The three battery capacity entities changed too,
from `device_class: energy` to `energy_storage`, but their statistic stays mean-based and their
history is untouched. [ADR 0011](../decisions/0011-energy-classes-follow-home-assistant.md) has
the reasoning for both.
