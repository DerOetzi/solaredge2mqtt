# Migrating from Environment Variables

!!! info "Affects the upgrade to 2.3.0"

    Relevant when you upgrade from a release **before 2.3.0**, published on 2026-01-24. If your
    installation already has a `config/configuration.yml`, this migration is behind you.

    Coming from that far back also means going through
    [the InfluxDB migration](influxdb-to-sqlite.md) when you reach 3.0.0.

Up to 2.3.0 the service was configured through environment variables, a `.env` file, or Docker
secrets. Since then it reads two YAML files.

## What changed

| File | Contents | Permissions |
|---|---|---|
| `configuration.yml` | Everything that is not sensitive | `644` |
| `secrets.yml` | Passwords, tokens, API keys, site and serial numbers | `600` |

Values in `configuration.yml` reference entries in `secrets.yml` through the `!secret` tag.

The gain is structure, a single place for sensitive values with restrictive permissions, editing
without rebuilding a container, and validation of the whole file against the settings model
rather than one variable at a time.

## Migration paths

### Automatic, on the next start

The easiest path, and the one that covers most installations.

When the service starts and `config/configuration.yml` is missing or empty, it reads environment
variables from three sources: the process environment, a `.env` file in the working directory,
and Docker secrets under `/run/secrets/`.

If it finds any, it validates them, writes both YAML files, and continues starting up. If it
finds none, it treats the installation as new, copies the example files in, and exits asking you
to edit them.

```bash
# First run, with the variables of your old installation still set
export SE2MQTT_MODBUS__HOST=192.168.1.100
export SE2MQTT_MQTT__BROKER=mqtt.example.com
solaredge2mqtt
```

Unset the variables before the next run. Once `configuration.yml` exists, it is the only source
the service reads.

### Manually, with the CLI tool

`solaredge2mqtt-migrate` performs the same conversion without starting the service, which lets
you preview the result.

```bash
# Preview, writes nothing
solaredge2mqtt-migrate --input .env --output-dir config --dry-run

# Convert, backing up any existing YAML files first
solaredge2mqtt-migrate --input .env --output-dir config --backup
```

| Option | Default | Meaning |
|---|---|---|
| `--output-dir`, `-o` | `.` (current directory) | Where the YAML files are written |
| `--dry-run`, `-d` | off | Print the result instead of writing files |
| `--backup`, `-b` | off | Rename existing files to `*.yml.backup.<timestamp>` first |
| `--input`, `-i` | `.env` | Path to the dotenv file to read |

The tool reads the same three sources as the automatic migration: the process environment, the
dotenv file, and Docker secrets under `/run/secrets/`. `--input` selects the dotenv file, so it
does not have to sit in the current directory:

```bash
solaredge2mqtt-migrate --input /etc/solaredge2mqtt/prod.env --output-dir config --dry-run
```

If the named file does not exist the tool says so and continues with the other two sources.

!!! note "The process environment wins"

    A variable set in the environment takes precedence over the same key in the dotenv file. Unset
    leftovers from the old installation if you want the file to decide.

### In Docker

=== "Auto-migration"

    Keep the environment variables for one start, then drop them.

    ```bash
    # First run: the service migrates into the mounted config directory
    docker run -d \
        -v $(pwd)/config:/app/config \
        -e SE2MQTT_MODBUS__HOST=192.168.1.100 \
        -e SE2MQTT_MQTT__BROKER=mqtt.example.com \
        ghcr.io/deroetzi/solaredge2mqtt:latest

    ls -la config/

    # Second run: no -e flags, the YAML files are used
    docker run -d \
        -v $(pwd)/config:/app/config \
        ghcr.io/deroetzi/solaredge2mqtt:latest
    ```

    With Compose, keep the `environment` section for the first `docker compose up`, then reduce
    it to what the container itself needs:

    ```yaml
    services:
      solaredge2mqtt:
        image: ghcr.io/deroetzi/solaredge2mqtt:latest
        volumes:
          - ./config:/app/config
        environment:
          - TZ=Europe/Berlin
    ```

=== "The tool in a container"

    ```bash
    cat > .env <<'ENV'
    SE2MQTT_MODBUS__HOST=192.168.1.100
    SE2MQTT_MQTT__BROKER=mqtt.example.com
    SE2MQTT_MQTT__PASSWORD=secret123
    ENV

    docker run --rm \
        -v $(pwd)/.env:/app/.env:ro \
        -v $(pwd)/config:/app/config \
        ghcr.io/deroetzi/solaredge2mqtt:latest \
        solaredge2mqtt-migrate --output-dir config --backup

    rm .env
    ```

    With Compose:

    ```bash
    docker compose run --rm solaredge2mqtt \
        solaredge2mqtt-migrate --output-dir config --backup
    docker compose up -d
    ```

=== "By hand"

    For a small setup it can be quicker to start from the examples than to migrate. The steps
    are in [Installation](../getting-started/installation.md#downloading-the-examples-yourself).

## How names map

Every variable was prefixed with `SE2MQTT_`. A double underscore separated a section from a
field and becomes one level of nesting.

```bash
SE2MQTT_INTERVAL=5
SE2MQTT_LOGGING_LEVEL=INFO
SE2MQTT_MODBUS__HOST=192.168.1.100
SE2MQTT_MODBUS__PORT=1502
```

```yaml
interval: 5
logging_level: INFO

modbus:
  host: 192.168.1.100
  port: 1502
```

### Lists

A digit appended directly to the field name, **not** separated by another double underscore,
becomes a list index:

```bash
SE2MQTT_MODBUS__METER0=true
SE2MQTT_MODBUS__METER1=false
SE2MQTT_MODBUS__METER2=false
```

```yaml
modbus:
  meter: [true, false, false]
```

Writing `METER__0` instead produces a dictionary with the key `"0"`, which the settings model
rejects.

### Secrets

Sensitive values are split into `secrets.yml` and referenced by a `!secret` tag, with the name
built from the section and the field:

```bash
SE2MQTT_MQTT__PASSWORD=secret123
SE2MQTT_MONITORING__PASSWORD=api_secret
```

```yaml
# configuration.yml
mqtt:
  password: !secret mqtt_password

monitoring:
  password: !secret monitoring_password
```

```yaml
# secrets.yml, written with 600 permissions
mqtt_password: "secret123"
monitoring_password: "api_secret"
```

The split is **not** driven by the field name. A field moves into `secrets.yml` when the settings
model declares it as a Pydantic `SecretStr`, which today means `mqtt.password`,
`mqtt.keyfile_password`, `monitoring.site_id`, `monitoring.password`, `wallbox.password`,
`wallbox.serial` and `weather.api_key`.

## Afterwards

1. **Check the files.** `ls -la config/` should show `configuration.yml` at `644` and
   `secrets.yml` at `600`.
2. **Check that every secret resolves.** Compare `grep "!secret" config/configuration.yml`
   against the keys in `secrets.yml`.
3. **Start and read the log.** A successful start logs `Loaded secrets from ...` and
   `Loaded configuration from ...`.
4. **Remove the old configuration.** Delete or rename `.env`, and strip the `environment`
   entries and any Docker secrets from your Compose file, keeping container-level variables such
   as `TZ`.
5. **Back it up.** `tar -czf config-backup-$(date +%Y%m%d).tar.gz config/`, or commit
   `configuration.yml` to git with `secrets.yml` excluded.

## Troubleshooting

### The service cannot find the configuration

It starts a migration you did not expect, or reports a missing file.

1. `ls -la config/` to confirm the directory and its contents.
2. `chmod 644 config/configuration.yml` and `chmod 600 config/secrets.yml`.
3. For Docker, confirm the mount: `docker inspect <container> | grep -A 10 Mounts`.

### A secret reference does not resolve

1. Compare both files. Names are case-sensitive, `!secret mqtt_password` matches
   `mqtt_password` and nothing else.
2. Quote values containing YAML special characters: `mqtt_password: "secret@123!"`.

### A value is rejected as the wrong type

The migration aborts with a validation error naming a field, for instance that `port` is not a
valid integer.

Quotation marks in `.env` are part of the value, they are not stripped. `PORT="1502"` reaches the
settings model as a string that still contains the quotes. Write values unquoted:

```bash
SE2MQTT_MODBUS__PORT=1502       # not "1502"
SE2MQTT_MODBUS__METER0=true     # not "true"
```

Everything that passes validation is written from the validated model, so the generated YAML
carries real types.

### The migration tool fails

1. `pip install --upgrade solaredge2mqtt`.
2. Check the `.env` format: one `KEY=VALUE` per line, no spaces around `=`, no quotes.
3. Check that the output directory is writable: `mkdir -p config && chmod 755 config`.

### The container cannot write the files

1. Create the directory before the first start: `mkdir -p config`.
2. Give the container ownership: `sudo chown -R 1000:1000 config/`.
3. On SELinux systems, add `:Z` to the mount.

More on container permissions is on the [Docker page](../deployment/docker.md#permissions-on-the-mounted-directory).

## Running several environments

```bash
solaredge2mqtt --config-dir /etc/solaredge2mqtt/production
solaredge2mqtt --config-dir /etc/solaredge2mqtt/testing
```

`secrets.yml` is plain YAML with no schema of its own, so it can be generated at deploy time from
Vault, AWS Secrets Manager or anything else that writes a file. Keep `configuration.yml` in
version control and render only the secrets per environment.
