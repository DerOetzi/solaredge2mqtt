# Modbus

The connection to the inverter. This section is required, the service does not start without it.

```yaml
modbus:
  host: 192.168.1.100             # IP address of your SolarEdge inverter

  # Optional, defaults shown
  # port: 1502
  # unit: 1                       # Modbus device address
  # timeout: 1                    # Connection timeout in seconds
  # retain: false               # Keep the last inverter, meter and battery payload on the broker

  # Device detection. Set a slot to false when nothing is installed there.
  # meter: [true, false, false]   # meter0, meter1, meter2
  # battery: [true, true]         # battery0, battery1

  # check_grid_status: false      # Requires extra hardware
  # storedge_control_enabled: false  # See the StorEdge Control page

  # Startup device detection retry, never gives up
  # startup_retry_delay: 30       # Initial delay between retries in seconds
  # startup_retry_max_delay: 300  # Delay doubles after each retry, capped here

  # debounce_cycles: 2            # Failed polls before the inverter is reported offline
```

`host` is the only field the service insists on. Everything else has a working default.

`debounce_cycles` sets how many consecutive failed polls it takes before the inverter is
published as offline, so a single dropped Modbus read does not flap the status topic.

`storedge_control_enabled` is covered on its own page,
[StorEdge Control](storedge-control.md).

## Meters and batteries you do not have

`meter` and `battery` are lists, one entry per slot. Set a slot to `false` when nothing is
physically installed there. Leaving an empty slot enabled produces decoding errors on every
startup, described under
[Troubleshooting](../troubleshooting.md#invalid-register-data-on-meter-detection).

## Startup retries

If the inverter is unreachable while devices are being detected, for instance during a brief
Modbus outage, the service retries instead of crashing. The delay starts at
`startup_retry_delay` and doubles after each attempt, capped at `startup_retry_max_delay`. It
never gives up.

## Leader and follower setups

SolarEdge inverters can be cascaded, with one leader and up to ten followers. The leader uses
the settings above; each follower is added to a `follower` list.

You can configure eleven inverters in total. Each one reports:

- its own power flow data,
- its own energy data, if enabled,
- and it contributes to the cumulative energy, power flow and production forecast.

### Cascaded over RS485

When followers sit on an RS485 bus behind the leader, they share the leader's TCP connection.
Only `unit`, the Modbus device address on that bus, is needed:

```yaml
modbus:
  host: 192.168.1.100
  port: 1502

  follower:
    - unit: 2
      meter: [false, false, false]
      battery: [false, false]
    - unit: 3
      meter: [true, false, false]
      battery: [true, false]
```

### Separate network connections

When an inverter has its own IP address, give it a `host`. Each follower with its own `host`
opens a dedicated TCP connection; the others fall back to the leader's.

```yaml
modbus:
  # Leader
  host: 192.168.1.100
  port: 1502

  follower:
    # Cascaded, shares the leader's connection
    - unit: 2
      meter: [false, false, false]
      battery: [false, false]

    # Own IP, port 1502 inherited from the leader
    - unit: 1
      host: 192.168.1.101
      meter: [true, false, false]
      battery: [true, false]

    # Own IP and a custom port
    - unit: 1
      host: 192.168.1.102
      port: 502
      meter: [false, false, false]
      battery: [true, true]
```

A follower without `port` uses the leader's port. A follower without `host` reuses the leader's
host and its connection.
