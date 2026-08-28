# Running the Service

## In the foreground

Useful while you are still shaping the configuration, because every log line lands in the
terminal.

```bash
# Reads ./config/
solaredge2mqtt

# Reads somewhere else
solaredge2mqtt --config-dir /path/to/config
```

Raise the detail level in `configuration.yml` when something is unclear:

```yaml
logging_level: DEBUG   # DEBUG, INFO, WARNING, ERROR or CRITICAL
```

## As a systemd service

For a permanent installation on a Linux host that is not running containers.

Install the package system-wide and prepare the configuration:

```bash
pip install -U solaredge2mqtt

sudo mkdir -p /etc/solaredge2mqtt
sudo curl -o /etc/solaredge2mqtt/configuration.yml \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
sudo curl -o /etc/solaredge2mqtt/secrets.yml \
    https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example

sudo chmod 600 /etc/solaredge2mqtt/secrets.yml
sudo nano /etc/solaredge2mqtt/configuration.yml
sudo nano /etc/solaredge2mqtt/secrets.yml
```

Write the unit to `/etc/systemd/system/solaredge2mqtt.service`:

```ini
[Unit]
Description=SolarEdge 2 MQTT Service
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/etc/solaredge2mqtt
ExecStart=/usr/local/bin/solaredge2mqtt --config-dir /etc/solaredge2mqtt
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now solaredge2mqtt

sudo systemctl status solaredge2mqtt
sudo journalctl -u solaredge2mqtt -f
```

!!! note "The user needs to read the configuration"

    `User=` has to be able to read `/etc/solaredge2mqtt/secrets.yml`, which is mode `600`. Either
    make that user the owner, or run as the owner. Do not loosen the permissions instead.

## In a container

See [Docker](../deployment/docker.md) and [Docker Compose](../deployment/docker-compose.md).
Both restart the service on their own once configured.

## What the service publishes about itself

Below the configured `topic_prefix`:

- `status/<service>` carries `online` or `offline` for each subservice, among them `modbus`,
  `wallbox`, `monitoring`, `storage` and `weather_api`.
- `logging` carries runtime log messages. MQTT's own warnings and errors are left out, so a
  broker problem cannot feed itself.

If a status flaps, raise `debounce_cycles` in that service's own section. Each page in the
[configuration reference](../configuration/index.md) documents the setting for its service.
