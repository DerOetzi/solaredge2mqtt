# Forecast

Predicts PV production with a machine learning model trained on your own history and current
weather.

```yaml
forecast:
  enable: true                            # Off by default

  # Optional, defaults shown
  # hyperparametertuning: false           # CPU intensive
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
