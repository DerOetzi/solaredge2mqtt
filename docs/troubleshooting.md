# Troubleshooting

## Invalid register data on meter detection

**Symptom.** Errors like these during startup device detection:

```
ERROR: Skipping meter2 due to invalid register data in device info
ERROR: Failed to decode register 'c_manufacturer' at address 40123: 'utf-8' codec can't decode byte...
```

**Cause.** Usually one of:

- a meter position is enabled in the configuration but no physical meter is installed there,
- the meter reports uninitialised or corrupted data,
- or there is a communication problem with the meter.

**If you have no meter at that position**, disable its detection. The `meter` list has one entry
per slot:

```yaml
modbus:
  meter:
    - true   # meter0
    - false  # meter1, disable if not installed
    - false  # meter2, disable if not installed
```

Restart the service afterwards.

**If you do have a meter there**, check the physical connection between inverter and meter,
confirm the meter is powered, look for communication errors in the inverter's own log, and
contact SolarEdge support if it persists.

!!! note "Only that device is skipped"

    The service keeps monitoring everything else when one meter fails to respond.

## The inverter is unreachable at startup

The service does not exit. It retries with exponential backoff, starting at
`startup_retry_delay` and doubling up to `startup_retry_max_delay`, and never gives up. Both are
documented under [Modbus](configuration/modbus.md#startup-retries).

If it never connects, check that `host`, `port` and `unit` are right, and that Modbus TCP is
enabled on the inverter. It is off by default on many SolarEdge units and has to be switched on
in the installer menu or SetApp.

## A status keeps flapping between online and offline

Raise `debounce_cycles` in the section of the service that is flapping. It requires that many
consecutive failed checks before `offline` is published:

```yaml
modbus:
  debounce_cycles: 2
```

The setting exists for [modbus](configuration/modbus.md),
[monitoring](configuration/monitoring.md), [wallbox](configuration/wallbox.md),
[weather](configuration/weather.md) and [storage](configuration/storage.md). It is not a
top-level option.

## Permission denied in Docker

Covered on the [Docker page](deployment/docker.md#permissions-on-the-mounted-directory),
including the caveat that the automatic ownership fix loosens the mode of `secrets.yml`.

## A secret is not found

The error names a secret that is missing from `secrets.yml`. Compare both files:

```bash
grep "!secret" config/configuration.yml
cat config/secrets.yml
```

Names are case-sensitive. `!secret mqtt_password` matches `mqtt_password`, not `MQTT_PASSWORD`.
Values containing `@`, `:`, `#` or a leading `!` need quotes.

## The forecast never produces anything

Forecasting needs at least 60 hours of continuous training data, plus
[location](configuration/index.md#basic-settings), [storage](configuration/storage.md) and
[weather](configuration/weather.md) all configured. A gap longer than an hour prevents that
stretch from becoming training data. A fresh installation is quiet for the first few days by
design.

Check that the optional dependencies are installed:

```bash
pip install -U "solaredge2mqtt[forecast]"
```

The Docker image already includes them.

## Weather automations broke after an upgrade

The `weather/current` topic now publishes canonical field names. `temp` became `temperature`,
`clouds` became `cloud_cover`, and `weather_id` became the WMO `condition_code`. The full list
is under [Weather](configuration/weather.md#the-published-payload).

## Getting more detail

```yaml
logging_level: DEBUG
```

Then read the log where your deployment puts it: the terminal, `docker logs`, or
`journalctl -u solaredge2mqtt -f`.

## Still stuck

- Ask on [Discord](https://discord.gg/QXfghc93pY).
- Open a [GitHub issue](https://github.com/DerOetzi/solaredge2mqtt/issues) with your
  `configuration.yml`, secrets removed, and the relevant log lines.
