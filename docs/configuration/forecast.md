# Forecast

Predicts PV production with a machine learning model trained on your own history and current
weather.

```yaml
forecast:
  enable: true                            # Off by default

  # Optional, defaults shown
  # hyperparametertuning: false           # CPU intensive
  # training_interval_hours: 0            # 0 picks the interval automatically
  # hyperparametertuning_interval_days: 7 # Only with hyperparametertuning
  # cachingdir: ~/.cache/se2mqtt_forecast # /app/cache in the Docker image
  # cache_size_limit_mb: 512
  # retain: false                        # Keep the last forecast on the broker
  # battery_target_soc: 98.0              # Target state of charge in percent
  # battery_charge_efficiency: 0.92       # Charge efficiency
  # production_threshold_wh: 500.0        # Counts as a production hour from here
```

Forecasting needs the optional dependencies:

```bash
pip install -U "solaredge2mqtt[forecast]"
```

The Docker image already includes them.

## Prerequisites

Three other sections have to be configured first:

| Requirement | Why |
|---|---|
| [`location`](index.md#basic-settings) | The model needs to know where the sun is |
| [`storage`](storage.md) | The training data comes from the local history |
| [`weather`](weather.md) | The prediction is driven by the current forecast |

On top of that:

- At least **60 hours of training data** must be collected before forecasting begins.
- Recording has to be continuous. A gap longer than an hour prevents that stretch from becoming
  training data.

A fresh installation therefore produces nothing for the first few days. That is expected.

## How often the model is retrained

Training data is written every hour, the model behind it is not rebuilt that often. Below 30 days
of history every new hour still shifts the prediction, so the model is retrained hourly. From 30
days on a single hour changes almost nothing and retraining drops to once a day.

Set `training_interval_hours` to a fixed number of hours to override that, for example `6` to
retrain four times a day regardless of the amount of history.

The hyperparameter search dominates the runtime of a training run and its result is stable over
weeks. With `hyperparametertuning` enabled it therefore runs on its own cadence, by default every
7 days. The retrainings in between reuse the parameters the last search found, so only the search
itself is skipped, not its result. `0` tunes on every training run again, the behaviour before
this setting existed.

## The model survives a restart

After every training run the model is written to a `model` directory below `cachingdir`, and it is
loaded again on the next start. A restart therefore keeps the schedule above instead of retraining
and searching immediately. Setting `cachingdir` to nothing disables this together with the
training cache, and every start trains from scratch.

The model is discarded and rebuilt from scratch whenever it no longer fits the current setup, for
example after an update that ships a new pvlearn release or after a change of `location`. That is
logged, needs no action and costs one training run.

In a container the cache directory is `/app/cache`. Mount it, as the compose file and the
[Docker deployment](../deployment/docker.md) do, or the model lives in the container's own layer
and a `docker compose down` or `docker rm` throws it away.

## The battery charge window

If a battery is detected over Modbus, the forecast also publishes when charging it from the
forecasted production should start. The goal is not to fill the battery as early as possible but
to flatten the day's feed-in peak, so the battery still has room when production is at its
strongest.

| Value | Meaning |
|---|---|
| `battery_charge_optimal_start_time` | Start of the first hour of the charge window |
| `battery_charge_duration` | Width of the window in hours, every started hour counted |
| `battery_charge_target_covered_today` | Whether today could cover `battery_target_soc` at all |

### How the window is found

All slots of the current day above `production_threshold_wh` are considered, including hours that
have already passed. A slot below the threshold is a wall: the window never grows past it, even
if production picks up again behind it.

The window starts as the single strongest slot of the day and grows one slot at a time until the
need is covered. In each step the neighbour before and the neighbour after the window are
compared by their forecasted production, and the larger one joins the window. A tie goes to the
later slot. Growing forwards is skipped whenever the added slot would fill the battery before the
end of the window, because that is exactly the case where the battery would be full before the
peak arrives. Once there is nothing left to add behind the window, that restriction is dropped
and the window grows forwards again.

The need itself is `battery_target_soc` minus the current charge, with
`battery_charge_efficiency` accounting for the loss on the way in.

### The charge power limits what a slot is worth

A battery that charges with at most 5 kW takes 5 kWh out of an hour, no matter whether that hour
produces 6 or 8 kWh. The service reads that limit from the battery over Modbus and caps every
slot with it, so the window does not come out too narrow and the start time not too late. Several
batteries add up. The cap only applies to the accumulated energy, never to the comparison between
two slots, which always uses the raw forecast, because that is what decides which hour is worth
shaving.

Two things are still assumed away. House consumption is ignored, so only part of the forecasted
production is really available for charging. A SolarEdge battery also throttles above roughly
90 percent state of charge, so the last stretch up to the target takes longer than the window
suggests.

### A start time in the past

The window describes the day, not the hours that happen to be left, so its start time can lie in
the past once the strongest hours have gone by. Read that the same way as an unreachable target:
charge from now on and take what the day still gives.

The start time moves later as the battery fills, because the need shrinks with it. A consumer
that is already charging can therefore also see a start time in the future. That means it is
running ahead of schedule, not that the value is wrong.

### When the day cannot cover the target

On a short winter day the window can end up too narrow for the need, since it has to be at least
need divided by charge power wide. The start time is then the beginning of the current hour,
because every remaining watt-hour is needed, and `battery_charge_target_covered_today` is `false`.
Nothing is published at all when no slot above the threshold lies on the current day, and neither
is anything published without a battery.

The flag is named after what it answers: whether the day as a whole could have covered the need.
It says nothing about the target still being within reach once the window has started, which is
what a start time in the past tells you.

## The shape of today's production

Four more values describe the whole current day, so a consumer can decide whether charging is
worth shifting at all:

| Value | Meaning |
|---|---|
| `energy_peak_today` | Output of the strongest production hour of the day, in Wh |
| `energy_peak_time_today` | When that hour starts, the earliest one if several tie |
| `energy_average_today` | Mean over the day's production hours, in Wh |
| `energy_median_today` | Median over the same hours, in Wh |

These cover the whole day just like the charge window, so they stay stable while the day runs.
The peak is also what the window anchors on.

A production hour is a slot above `production_threshold_wh`, 500 Wh by default. The weak hours
around sunrise and sunset would otherwise pull the average and the median down and make a good
day look like a mediocre one. The same threshold decides which slots the charge window may use
and which hour counts as the peak, so on a small plant it is worth lowering. A day that stays
below it everywhere reports `0` for all four values and gets no charge window. `0` counts every
slot with any production.

## Using the forecast in Home Assistant

The Energy Dashboard can consume these forecasts through a companion integration:

[SolarEdge2MQTT Forecast](https://github.com/DerOetzi/solaredge2mqtt_forecast)

It reads the forecast topics and registers itself in Home Assistant as a solar forecast provider.

The wiring between this service and the forecast core is described in
[decision 0001](../decisions/0001-pvlearn-extraction-wiring.md).
