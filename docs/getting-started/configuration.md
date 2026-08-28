# First Configuration

The service reads two YAML files from its configuration directory.

| File | Contents | Permissions |
|---|---|---|
| `configuration.yml` | Everything that is not sensitive | `644` |
| `secrets.yml` | Passwords, tokens, API keys, site and serial numbers | `600` |

Both are created for you on the first start, copied from the packaged examples. Edit them and
start the service again.

## Where the files live

By default the service looks in `./config/`, relative to the working directory. `--config-dir`
points it somewhere else:

```bash
# Default, ./config/
solaredge2mqtt

# Somewhere else
solaredge2mqtt --config-dir /etc/solaredge2mqtt

solaredge2mqtt --help
```

In a container the path is always `/app/config`. The volume mount decides where that is on the
host.

The SQLite history is written into the same directory, so it needs to survive restarts.

## The minimum that must be set

Two sections have no usable defaults, the service will not start without them:

```yaml
modbus:
  host: 192.168.1.100   # Your inverter
  port: 1502

mqtt:
  broker: mqtt.example.com
  username: mqtt_user
  password: !secret mqtt_password
```

```yaml
# secrets.yml
mqtt_password: "your_actual_password"
```

Everything else is optional and off or defaulted until you turn it on. The
[configuration reference](../configuration/index.md) covers each section.

## Keeping secrets out of the main file

The `!secret` tag reads a value from `secrets.yml` by name:

```yaml
# configuration.yml
mqtt:
  broker: mqtt.example.com
  password: !secret mqtt_password
```

```yaml
# secrets.yml
mqtt_password: "your_actual_password"
```

The name on the right of `!secret` is just a key in `secrets.yml`. It is case-sensitive and has
to match exactly.

This keeps `configuration.yml` safe to commit and to paste into a support thread, while
`secrets.yml` stays local with restrictive permissions.

### Which fields belong in secrets.yml

These are the credentials the service knows about. The packaged example already references them
with `!secret`, so you only fill in the values:

| Section | Fields |
|---|---|
| `mqtt` | `password`, `keyfile_password` |
| `monitoring` | `site_id`, `password` |
| `wallbox` | `password`, `serial` |
| `weather` | `api_key` |

The `!secret` tag works for **any** setting, so move anything else you consider sensitive there
too.

!!! tip "Quote awkward values"

    `secrets.yml` is plain YAML. A value containing `@`, `:`, `#` or a leading `!` needs quotes:
    `mqtt_password: "secret@123!"`.

## Checking that it worked

A successful start logs both files:

```
INFO | Loaded secrets from config/secrets.yml
INFO | Loaded configuration from config/configuration.yml
```

If you instead see a line about migrating from environment variables, the service did not find
`configuration.yml` where it looked. Check the path, and the volume mount if you are running in a
container.

## Next steps

- [Run the service](running.md) in the foreground or under systemd.
- Go through the [configuration reference](../configuration/index.md) for the features you want.
