# Wallbox

Monitors a SolarEdge Wallbox over its local REST API.

```yaml
wallbox:
  host: 192.168.1.101                 # Wallbox IP address
  password: !secret wallbox_password  # Admin password
  serial: !secret wallbox_serial      # Wallbox serial number

  # Optional, defaults shown
  # retain: false      # Keep the last wallbox payload on the broker
  # debounce_cycles: 2  # Failed requests before the wallbox is reported offline
```

All three are needed. With any of them missing the service stays switched off.

`debounce_cycles` sets how many consecutive failed requests it takes before the wallbox is
published as offline. A wallbox that drops off wifi briefly then stops flapping its status.

```yaml
# secrets.yml
wallbox_password: "your_wallbox_admin_password"
wallbox_serial: "ABC123456"
```

The password is the wallbox's own admin password, not your SolarEdge monitoring account. The
serial number is on the device label.

This is the local wallbox integration. An EV charger attached to your SolarEdge monitoring
account is a different feature, covered under [Monitoring](monitoring.md#ev-charger-monitoring-and-control).
