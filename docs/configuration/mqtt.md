# MQTT

The broker connection. This section is required, the service does not start without it.

```yaml
mqtt:
  broker: mqtt.example.com         # IP address or hostname of the broker
  username: mqtt_user              # Omit both if your broker allows anonymous access
  password: !secret mqtt_password

  # Optional, defaults shown
  # client_id: solaredge2mqtt      # MQTT client identifier
  # port: 1883                     # 8883 is the usual port for TLS
  # topic_prefix: solaredge        # Prefix for every topic the service publishes
  # logging_level: ERROR           # Minimum level forwarded to the logging topic

  # TLS, all optional and only used when use_tls is true
  # use_tls: false
  # ca_certs: /path/to/ca.pem      # CA bundle, for a privately signed broker certificate
  # certfile: /path/to/client.pem  # Client certificate, for mutual TLS
  # keyfile: /path/to/client.key   # Private key matching certfile
  # keyfile_password: !secret mqtt_keyfile_password  # Only if the key is encrypted
  # tls_verify: true               # Set to false to skip certificate validation
```

`broker` is the only field the service insists on.

```yaml
# secrets.yml
mqtt_password: "your_actual_password"
mqtt_keyfile_password: "your_actual_key_password"
```

## TLS and client certificates

`ca_certs`, `certfile` and `keyfile` are only used when `use_tls` is enabled, and all three are
unset by default.

If your broker authenticates clients by certificate rather than, or in addition to, a password,
set `certfile` and `keyfile` to the client keypair. `keyfile_password` is needed only when the
private key itself is encrypted.

Leave `tls_verify` at `true` unless you are deliberately testing against a self-signed
certificate you cannot add to the trust store.

## Operational topics

Below the configured `topic_prefix`, the service publishes two things about itself:

- `status/<service>` carries `online` or `offline` for each subservice: `modbus`, `wallbox`,
  `monitoring`, `storage` and `weather_api`.
- `logging` carries runtime log messages at `logging_level` and above. MQTT's own warnings and
  errors are excluded, so a broker problem cannot feed itself.

Each of those services has its own `debounce_cycles` setting, documented on its page, which
decides how many consecutive failed checks it takes before a change is published.

## Retained messages

A retained message stays on the broker after it is published, so a client that subscribes later
is handed the last value straight away instead of waiting for the next one.

Nothing is retained by default. Each service decides for itself through a `retain` flag in its
own section, documented on that service's page. There is no global switch.

Retaining is useful for values a dashboard should show immediately after a restart. It is
unhelpful for anything an automation reacts to as an event, because a subscriber receives the
stale value the moment it connects.
