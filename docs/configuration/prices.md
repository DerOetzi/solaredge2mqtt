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
    enabled. With `storage.enable: false` this section does nothing.

A single flat rate per direction is all this supports. Time-of-use tariffs with a different price
per hour are not modelled.
