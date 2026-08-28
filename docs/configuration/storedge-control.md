# StorEdge Battery Control

On SolarEdge StorEdge and backup-capable systems, the battery's charge and discharge behaviour
can be read and written over Modbus. That covers the storage control mode, the AC charge policy,
the backup reserve, and, while in Remote Control mode, the default and timed charge and
discharge commands.

```yaml
modbus:
  storedge_control_enabled: true
```

!!! warning "This writes to your battery"

    The setting is off by default. Unlike passive telemetry, changing these values affects real
    battery cycling.

Once enabled, the current values are published as part of the inverter payload under
`storedge_control`.

## Command topics

Nine topics accept writes:

```
modbus/inverter/storedge/control_mode
modbus/inverter/storedge/ac_charge_policy
modbus/inverter/storedge/ac_charge_limit
modbus/inverter/storedge/backup_reserved_setting
modbus/inverter/storedge/default_mode
modbus/inverter/storedge/command_timeout
modbus/inverter/storedge/command_mode
modbus/inverter/storedge/charge_limit
modbus/inverter/storedge/discharge_limit
```

A payload is either a bare value or a JSON object. Publishing `4` or `{"mode": 4}` to
`control_mode` switches the battery to Remote Control mode.

| Topic suffix | Field | Range | Read-back field under `storedge_control` |
|---|---|---|---|
| `control_mode` | `mode` | 0 to 4 (0 Disabled, 1 Maximize Self Consumption, 2 Time of Use, 3 Backup Only, 4 Remote Control) | `storage_control_mode` |
| `ac_charge_policy` | `policy` | 0 to 3 | `storage_ac_charge_policy` |
| `ac_charge_limit` | `limit` | 0 or more, kWh or percent depending on the policy | `storage_ac_charge_limit` |
| `backup_reserved_setting` | `percentage` | 0 to 100 | `storage_backup_reserved_setting` |
| `default_mode` | `mode` | 0 to 7 | `storage_default_mode` |
| `command_timeout` | `seconds` | 0 to 86400 | `remote_control_command_timeout` |
| `command_mode` | `mode` | 0 to 7 | `remote_control_command_mode` |
| `charge_limit` | `limit` | 0 or more, in watts | `remote_control_charge_limit` |
| `discharge_limit` | `limit` | 0 or more, in watts | `remote_control_discharge_limit` |

The write suffixes are shorter than the read-back names on purpose. The `storedge/` path segment
already says which block this is, so the topics drop the redundant `storage_` and
`remote_control_` prefixes. The read-back payload keeps the full SolarEdge protocol name of the
SunSpec register.

!!! note "Two different limits"

    `charge_limit` and `discharge_limit` here are the Remote Control power limits in watts. They
    are not the same as `ac_charge_limit`, which is the AC charging limit in kWh or percent.

## When a write takes effect

`control_mode`, `ac_charge_policy`, `ac_charge_limit` and `backup_reserved_setting` always take
effect.

The other five only take effect once `storage_control_mode` is `4`, Remote Control. Writing to
them in any other mode is rejected and logged, because SolarEdge ignores them there.

## Skipped and forced writes

If the value you publish already matches the last value read back from the inverter, the write
is skipped. These registers do not need to be exercised more than necessary.

To write anyway, for instance when you suspect the cached value is stale, add `force`:

```json
{"mode": 4, "force": true}
```

Force only bypasses the no-op check. It does not bypass the Remote Control gate above.

## Home Assistant entities

With [auto discovery](home-assistant.md) enabled and `storedge_control_enabled: true`, all nine
fields appear as native entities on the inverter device:

- **Select** entities for `control_mode`, `ac_charge_policy`, `default_mode` and `command_mode`.
  The dropdown shows SolarEdge's own mode names, and Home Assistant translates the label back to
  the numeric value before publishing.
- **Number** entities for `ac_charge_limit`, `backup_reserved_setting`, `command_timeout`,
  `charge_limit` and `discharge_limit`.

Each entity uses the command topic documented above, so changing a value in the Home Assistant
interface is the same as publishing to MQTT directly. The five Remote-Control-gated fields say so
in their entity name.
