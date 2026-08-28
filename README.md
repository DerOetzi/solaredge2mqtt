# SolarEdge 2 MQTT Service

[![License](https://img.shields.io/github/license/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/blob/main/LICENSE) [![Release](https://img.shields.io/github/v/release/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/releases/latest) [![Build Status](https://img.shields.io/github/actions/workflow/status/DerOetzi/solaredge2mqtt/build_project.yml?branch=main)](https://github.com/DerOetzi/solaredge2mqtt/actions/workflows/build_project.yml) [![PyPI version](https://img.shields.io/pypi/v/solaredge2mqtt.svg)](https://pypi.org/project/solaredge2mqtt/) [![Discord Chat](https://img.shields.io/discord/1196540254686032014)](https://discord.gg/QXfghc93pY) [![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-yellow)][buymecoffee-link]

SolarEdge2MQTT reads power data from a SolarEdge inverter over Modbus TCP and publishes it to an
MQTT broker. It is built for home automation: real-time power flow, battery state, grid import and
export, and meter readings, all as MQTT topics that Home Assistant can discover on its own.

Beyond the inverter itself, the service can log in to your SolarEdge monitoring account to read
module-level production and control an EV charger, keep a local history in a SQLite file, and
forecast tomorrow's production from that history and live weather data.

**📖 Full documentation: [deroetzi.github.io/solaredge2mqtt](https://deroetzi.github.io/solaredge2mqtt/)**

## 🔧 Features

- 📡 **Modbus communication** with SolarEdge inverters over TCP
- 🧠 **Leader/follower support** for cascaded and physically separate multi-inverter setups
- ⚡ **Power flow monitoring**: inverter production, battery charge and discharge, grid import
  and export, consumption and generation from the Modbus meters
- 🔋 **StorEdge battery control**, including remote charge and discharge limits
- 🕸️ **MQTT integration** with optional TLS, for Home Assistant and anything else
- 🔄 **Home Assistant auto discovery**
- 💡 **Local history** in a SQLite database, no external service required
- 📈 **PV production forecasting** from a machine learning model, fed by the local history and
  OpenWeatherMap
- 💸 **Price-based savings calculation** for consumption and export
- 🔌 **SolarEdge Wallbox monitoring** over its REST API
- 🌐 **Module-level monitoring** through the SolarEdge monitoring site, no API key needed
- 🚗 **EV charger monitoring and control** through the same account
- 🐳 **Docker and Docker Compose** images for `linux/amd64` and `linux/arm64`

## 🚀 Quick Start

```bash
pip install -U solaredge2mqtt

# Writes example config files into ./config/ and exits
solaredge2mqtt
```

Fill in the inverter address and your MQTT broker in `config/configuration.yml`, put the broker
password in `config/secrets.yml`, and start it again.

Or with Docker:

```bash
mkdir -p config
docker run -d --name solaredge2mqtt \
    -v $(pwd)/config:/app/config \
    -e "TZ=Europe/Berlin" \
    --restart unless-stopped \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

Step by step, with every option explained:
**[Installation guide](https://deroetzi.github.io/solaredge2mqtt/getting-started/installation/)**

## 📚 Documentation

| Guide | What it covers |
|---|---|
| [Getting Started](https://deroetzi.github.io/solaredge2mqtt/getting-started/installation/) | Installation, first configuration, running as a service |
| [Configuration Reference](https://deroetzi.github.io/solaredge2mqtt/configuration/) | Every option, one page per service |
| [Deployment](https://deroetzi.github.io/solaredge2mqtt/deployment/docker/) | Docker, Docker Compose, the full stack with Grafana |
| [Migration](https://deroetzi.github.io/solaredge2mqtt/migration/influxdb-to-sqlite/) | Upgrading to 3.0.0, moving an InfluxDB history into the local storage |
| [Troubleshooting](https://deroetzi.github.io/solaredge2mqtt/troubleshooting/) | Known symptoms and what to do about them |
| [Architecture Decisions](https://deroetzi.github.io/solaredge2mqtt/decisions/) | Why the project is built the way it is |
| [Contributing](CONTRIBUTING.md) | Development setup, tests, pull requests |

## 💬 Contact and Feedback

For questions and discussion, join us on Discord.

[![Discord Banner](https://discordapp.com/api/guilds/1196540254686032014/widget.png?style=banner2)](https://discord.gg/QXfghc93pY)

Ideas, suggestions and problems are welcome as an
[issue](https://github.com/DerOetzi/solaredge2mqtt/issues).

## ❤️ Support

If you like this project, I would appreciate a small contribution.

[![BuyMeCoffee][buymecoffee-shield]][buymecoffee-link]

[buymecoffee-link]: https://www.buymeacoffee.com/deroetzik
[buymecoffee-shield]: https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png
