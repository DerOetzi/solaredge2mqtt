# Prices

Turns energy readings into money by attaching a price to what you draw from the grid and what
you deliver to it.

```yaml
prices:
  consumption: 0.30  # Price paid per kWh drawn from the grid
  delivery: 0.08     # Price received per kWh delivered to the grid
  currency: EUR      # Currency label
```

All three have no default. A price only counts when `currency` is set alongside it.

!!! warning "`currency` is not optional"

    A price is only considered configured when both the amount **and** `currency` are set. Set
    `consumption` and `delivery` without it and the calculation stays switched off silently, with
    nothing published and no error in the log.

    The label is also what Home Assistant shows as the unit of the resulting entities.

The two amounts are per kilowatt hour. The service does not convert between currencies, it only
multiplies, so `currency` is a label rather than a conversion instruction. Use whatever your
tariff is billed in.

Either direction works on its own. Configure `consumption` alone to only track what you saved,
or `delivery` alone to only track what you earned.

!!! note "Requires storage"

    Savings are computed from the accumulated history, so [storage](storage.md) has to be
    enabled. With `storage.enable: false` this section does nothing and a warning is logged at
    startup.

## Time-of-use tariffs

For a tariff whose price depends on the time of day, the weekday or the season, add a
`schedule`. Each entry sets a price for a time window:

```yaml
prices:
  consumption: 0.39  # Used whenever no entry matches
  delivery: 0.05
  currency: USD
  schedule:
    - name: Summer peak
      months: [6, 7, 8, 9]
      weekdays: [mon, tue, wed, thu, fri]
      start: "16:00"
      end: "21:00"
      consumption: 0.62
    - name: Winter peak
      months: [1, 2, 3, 4, 5, 10, 11, 12]
      start: "16:00"
      end: "21:00"
      consumption: 0.49
    - name: Night
      start: "22:00"
      end: "06:00"
      consumption: 0.31
```

| Key | Default | Meaning |
|---|---|---|
| `name` | none | Label for your own reference |
| `months` | every month | Months the entry applies to, `1` to `12` |
| `weekdays` | every day | Any of `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun` |
| `start` | `"00:00"` | First minute of the window, on a quarter hour |
| `end` | `"24:00"` | End of the window, excluded, on a quarter hour |
| `consumption` | none | Price per kWh drawn from the grid inside the window |
| `delivery` | none | Price per kWh delivered to the grid inside the window |

How a price is chosen for each quarter hour:

- Times are local, in the time zone the service runs in. Daylight saving time is followed, so a
  window from 17:00 to 21:00 always means 17:00 to 21:00 on the clock.
- The entries are checked from top to bottom, and the first one that matches and has a price for
  the direction wins. An entry with only `consumption` set leaves `delivery` to the following
  entries.
- When no entry matches, the flat `consumption` or `delivery` above applies, or nothing is
  charged when that is not set either.
- An `end` at or before `start` runs over midnight. The hours after midnight still belong to the
  day the window started, so a Friday night window from `22:00` to `06:00` also covers Saturday
  morning until 06:00. Equal `start` and `end` cover the whole day.

The `currency` is still required. A schedule entry with a price counts as configured just like
a flat price.

Every hour stores the money it earned or cost, summed per quarter hour, plus the energy-weighted
mean price of that hour. A changed schedule applies from the next aggregation on, which also
recalculates the last two hours. Older hours keep the prices they were calculated with.

Holidays are not modelled yet. A tariff that treats them like a Sunday prices them as a
weekday.
