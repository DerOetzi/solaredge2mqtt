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

## Optimal battery charge start time

If a battery is detected over Modbus, the forecast also publishes
`battery_charge_optimal_start_time`. It is the earliest moment at which charging from the
strongest remaining forecasted production slots should start.

The slots are sorted by output and accumulated until `battery_target_soc` is covered, with
`battery_charge_efficiency` accounting for the loss on the way in. Only slots on the current day
are considered. If today's remaining production cannot cover the need, no start time is
published.

## Using the forecast in Home Assistant

The Energy Dashboard can consume these forecasts through a companion integration:

[SolarEdge2MQTT Forecast](https://github.com/DerOetzi/solaredge2mqtt_forecast)

It reads the forecast topics and registers itself in Home Assistant as a solar forecast provider.

The wiring between this service and the forecast core is described in
[decision 0001](../decisions/0001-pvlearn-extraction-wiring.md).
