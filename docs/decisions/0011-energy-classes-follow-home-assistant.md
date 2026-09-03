# 0011 — Stored energy and session energy get their own Home Assistant classes

**Status:** Accepted
**Context:** Home Assistant validates `device_class` against `state_class` and, since 2026.9.0, logs a warning for every entity that gets the pair wrong:

```
Entity <id> is using state class 'measurement' which is impossible considering device class ('energy') it is using; expected None or one of 'total_increasing', 'total'
```

Four entities published by this service were affected, all of them through one shared sensor type, `ENERGY_MEASUREMENT_WH` (`energy` / `measurement` / `Wh`): the three battery capacity fields `maximum_energy`, `available_energy` and `rated_energy`, and the EV charger's `session_energy`. The two are not the same kind of value, so the shared type had to be split rather than corrected in place.

## Decision 1: battery capacities are `energy_storage`, not `energy`

**Decision:** The battery capacity fields use a new `ENERGY_STORAGE_WH` sensor type — `device_class: energy_storage`, `state_class: measurement`, unit `Wh`.

**Context:** These fields describe how much energy the battery holds or can hold right now. They rise and fall, they do not accumulate, so `measurement` is the state class that describes them and it is the one that had to survive. `energy_storage` is Home Assistant's device class for exactly that, and it accepts `measurement` and nothing else.

Changing the state class to `total_increasing` instead was rejected: it would have silenced the warning while telling Home Assistant that a falling battery level is a meter reset.

**Consequence:** No statistics migration. `energy_storage` keeps the mean-based statistic these entities already had, so their history stays intact and continues as before.

## Decision 2: EV charger session energy is `total_increasing`

**Decision:** `session_energy` reuses the existing `ENERGY_WH` type — `device_class: energy`, `state_class: total_increasing`, unit `Wh`.

**Context:** This value really does accumulate over a charging session and drops back to zero when the next one starts. That reset is what `total_increasing` exists for: Home Assistant treats a drop as the start of a new cycle rather than as negative consumption.

Moving it to `energy_storage` alongside the battery fields was rejected. It would have matched the old state class and needed no migration, but it would describe a session counter as a storage level and keep it out of the energy dashboard.

**Consequence:** The long-term statistic for this entity changes from mean/min/max to sum. Home Assistant would raise a repair issue over changed statistics for an entity that already existed under the old class, requiring the old measurement-type statistics to be deleted under Developer Tools → Statistics before the sum statistic starts — but the EV charger integration this entity belongs to has not shipped yet, so no installation carries the old class and the migration step does not apply to anyone.
