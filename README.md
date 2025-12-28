# SolarEdge 2 MQTT Service

[![License](https://img.shields.io/github/license/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/blob/main/LICENSE) [![Release](https://img.shields.io/github/v/release/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/releases/latest) [![Build Status](https://img.shields.io/github/actions/workflow/status/DerOetzi/solaredge2mqtt/build_project.yml?branch=main)](https://github.com/DerOetzi/solaredge2mqtt/actions/workflows/build_project.yml) [![PyPI version](https://img.shields.io/pypi/v/solaredge2mqtt.svg)](https://pypi.org/project/solaredge2mqtt/) [![Discord Chat](https://img.shields.io/discord/1196540254686032014)](https://discord.gg/QXfghc93pY) [![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-donate-yellow)][buymecoffee-link]

The SolarEdge2MQTT service facilitates the retrieval of power data from SolarEdge inverters and its publication to an MQTT broker. Ideal for integrating SolarEdge inverters into home automation systems, this service supports real-time monitoring of power flow and additional parameters via Modbus. 

Users can optionally collect panel energy production and power data directly from the SolarEdge monitoring site, without employing the API, by leveraging their monitoring platform account.

## 🔧 Features

SolarEdge2MQTT provides a comprehensive feature set for power monitoring, home automation integration, and advanced analysis. Key capabilities include:

- 📡 **Modbus communication** with SolarEdge inverters (via TCP/IP)
- 🧠 **Leader/follower support** for multi-inverter cascaded setups
- ⚡ **Power flow monitoring**, including:
  - Inverter production
  - Battery status and charge/discharge
  - Grid import/export
  - Consumption and generation via Modbus meters
- 🕸️ **MQTT integration** for use with Home Assistant and other systems
- 🔄 **Home Assistant auto discovery** support (optional)
- 📈 **PV production forecasting** using a built-in machine learning model  
  → uses live weather data from OpenWeatherMap and historical data from InfluxDB
- 💡 **Data logging to InfluxDB** (raw and aggregated values)
- 💸 **Price-based savings calculation** for consumption and export
- 🔌 **SolarEdge Wallbox monitoring** via REST API
- 🌐 **Module-level monitoring** by retrieving data directly from the SolarEdge monitoring site (no API key needed)
- 🐳 **Docker and Docker Compose support** for easy deployment
- 🧪 **Console mode** for development and testing


It also enables the monitoring of SolarEdge Wallbox via the REST API and supports saving all values into InfluxDB for advanced visualization.

## Contact and Feedback

For inquiries, feel free to reach out on Discord.

[![Discord Banner](https://discordapp.com/api/guilds/1196540254686032014/widget.png?style=banner2)](https://discord.gg/QXfghc93pY)

We highly value your input. Share your ideas, suggestions, or issues by opening an [issue](https://github.com/DerOetzi/solaredge2mqtt/issues). Your feedback is eagerly awaited.

## Support

If you like this project, I would appreciate a small contribution.

[![BuyMeCoffee][buymecoffee-shield]][buymecoffee-link]

## Configuration

SolarEdge2MQTT uses YAML-based configuration files for easy and structured setup. Configuration is stored in two files in the `config/` directory:

- **`config/configuration.yml`**: Contains all non-sensitive settings
- **`config/secrets.yml`**: Contains sensitive data (passwords, tokens, API keys)

You can download the example files from the `config/` directory:
- [configuration.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/config/configuration.yml.example)
- [secrets.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/config/secrets.yml.example)

Rename them to `configuration.yml` and `secrets.yml`, then modify the values to meet your needs.

### Migration from Environment Variables

If you're upgrading from a previous version that used environment variables or `.env` files, SolarEdge2MQTT will automatically migrate your configuration on first run:

1. **Automatic Migration**: When no YAML configuration files exist (or they're empty), the service automatically creates them from your environment variables in the `config/` directory
2. **Manual Migration**: Use the migration tool for more control:
   ```bash
   solaredge2mqtt-migrate --input .env --output-dir config
   ```
   
   The migration tool supports:
   - `--dry-run`: Preview changes without writing files
   - `--backup`: Create backups of existing files
   - Custom input/output paths

After migration, sensitive values are automatically separated into `config/secrets.yml` and referenced in `config/configuration.yml` using the `!secret` tag.

### Secret References

To keep sensitive data secure, use the `!secret` tag in your configuration:

```yaml
# configuration.yml
mqtt:
  broker: mqtt.example.com
  password: !secret mqtt_password

# secrets.yml
mqtt_password: "your_actual_password"
```

The available configuration options are listed below:

### Basic configuration

```yaml
# Interval between data retrieval requests (in seconds)
interval: 5

# Logging verbosity: DEBUG, INFO, WARNING, ERROR, or CRITICAL
logging_level: INFO

# Location for weather and forecast services
location:
  latitude: 52.520008
  longitude: 13.404954

# Set to true if you have additional producers
powerflow:
  external_production: false
```

### Basic Modbus configuration

```yaml
modbus:
  host: 192.168.1.100  # IP address of your SolarEdge inverter
  port: 1502           # Modbus port (default: 1502)
  timeout: 1           # Connection timeout in seconds
  unit: 1              # Unit address (default: 1)
  
  # Enable or disable meter detection (default: true)
  meter:
    - true  # meter0
    - true  # meter1
    - true  # meter2
  
  # Enable or disable battery detection (default: true)
  battery:
    - true  # battery0
    - true  # battery1
  
  # Check grid status (requires extra hardware)
  check_grid_status: false
```

### Leader/follower setup

SolarEdge inverters support a cascading setup, where one inverter acts as the leader and up to ten others act as followers.

- For the leader inverter, use the basic Modbus settings described above.
- For each follower inverter, add them to the configuration as shown below.

```yaml
modbus:
  # Leader configuration
  host: 192.168.1.100
  port: 1502
  
  # Follower inverters
  follower:
    - unit: 2
      meter: [false, false, false]
      battery: [false, false]
    - unit: 3
      meter: [true, false, false]
      battery: [true, false]
```

You can configure up to 11 inverters in total: one leader and up to 10 followers. Each configured inverter will report:

- individual power flow data
- individual energy data (if enabled)
- cumulative energy and power flow data
- cumulative production forecasts (if forecasting is enabled)

This setup allows for comprehensive multi-inverter support in systems with cascaded SolarEdge installations.

### MQTT configuration

```yaml
mqtt:
  client_id: solaredge2mqtt        # MQTT client identifier
  broker: mqtt.example.com         # IP address of MQTT broker
  port: 1883                       # MQTT port (default: 1883)
  username: mqtt_user              # MQTT username
  password: !secret mqtt_password  # Use !secret to reference secrets.yml
  topic_prefix: solaredge          # MQTT topic prefix
```

**Note**: Store your password securely in `secrets.yml`:
```yaml
# secrets.yml
mqtt_password: "your_actual_password"
```
### Retain Configuration

By default, MQTT messages are not retained. You can configure the retain flag for each message type:

```yaml
energy:
  retain: false

forecast:
  retain: false

homeassistant:
  retain: false

monitoring:
  retain: false

powerflow:
  retain: false

wallbox:
  retain: false

weather:
  retain: false
```

### Monitoring

To enable panel energy and power value retrieval from the SolarEdge monitoring platform:

```yaml
monitoring:
  site_id: !secret monitoring_site_id     # Your SolarEdge site ID (store in secrets.yml)
  username: "user@example.com"             # SolarEdge platform username
  password: !secret monitoring_password    # Store in secrets.yml
  retain: false
```

Remember to add the site_id and password to `secrets.yml`:
```yaml
# secrets.yml
monitoring_site_id: "12345678"
monitoring_password: "your_monitoring_password"
```

### Wallbox

For monitoring SolarEdge Wallbox:

```yaml
wallbox:
  host: 192.168.1.101                     # Wallbox IP address
  password: !secret wallbox_password      # Admin password (store in secrets.yml)
  serial: !secret wallbox_serial          # Wallbox serial number (store in secrets.yml)
  retain: false
```

Add the password and serial to `secrets.yml`:
```yaml
# secrets.yml
wallbox_password: "your_wallbox_admin_password"
wallbox_serial: "ABC123456"
```

### Home Assistant Auto Discovery

Enable Home Assistant auto discovery:

```yaml
homeassistant:
  enable: true                 # Enable auto discovery
  topic_prefix: homeassistant  # MQTT discovery topic prefix
  retain: false
```

_To remove entities, disable the feature, restart SolarEdge2MQTT first, then restart Home Assistant._

### InfluxDB

Configure InfluxDB for data storage:

```yaml
influxdb:
  host: http://localhost           # InfluxDB host
  port: 8086                       # InfluxDB port (default: 8086)
  token: !secret influxdb_token    # Access token (store in secrets.yml)
  org: my_org                      # Organization ID
  bucket: solaredge                # Bucket name (default: solaredge)
  retention_raw: 25                # Raw data retention in hours
  retention: 63072000              # Aggregated data retention in seconds (2 years)
```

Add the token to `secrets.yml`:
```yaml
# secrets.yml
influxdb_token: "your_influxdb_token_with_full_access"
```

**Note**: The token requires full access as the service manages buckets and tasks.

### Price Configuration

Calculate savings and earnings by specifying energy costs. Requires InfluxDB.

```yaml
prices:
  consumption: 0.30  # Price paid per kWh from grid
  delivery: 0.08     # Price received per kWh delivered to grid
```

### Weather

Integrate real-time weather data from OpenWeatherMap:

```yaml
weather:
  api_key: !secret weather_api_key  # OpenWeatherMap API key (store in secrets.yml)
  language: en                       # Language for weather data (default: en)
  retain: false
```

Add the API key to `secrets.yml`:
```yaml
# secrets.yml
weather_api_key: "your_openweathermap_api_key"
```

To access weather data, you need an OpenWeatherMap account, an API key, and a [subscription](https://home.openweathermap.org/subscriptions) to the One-Call API. Visit [OpenWeatherMap](https://openweathermap.org/) for more information.

### Forecast

The service features machine learning-based PV production forecasting. Requires [location](#basic-configuration), [InfluxDB](#influxdb), and [weather](#weather) configuration.

```yaml
forecast:
  enable: false                      # Enable forecasting (default: false)
  hyperparametertuning: false        # Enable hyperparameter tuning (CPU intensive)
  cachingdir: ~/.cache/se2mqtt_forecast  # Cache directory for pipeline results
  retain: false
```

**Prerequisites**:
- Minimum 60 hours of training data must be collected before forecasting begins
- Data recording must be consistent (gaps longer than an hour prevent training data collection)

> **Note**: Forecast service is not available for `arm/v7` architectures due to dependency compatibility issues.

## Running the service

Each method provides different levels of control and isolation, suitable for various use cases from development to production deployment.

### In the Console

For development and testing environments:

1. **Preparation**: Ensure Python >=3.11, <=3.13 is installed.
2. **Installation**: 
   ```bash
   pip install -U solaredge2mqtt
   ```
   
   For forecast functionality:
   ```bash
   pip install -U solaredge2mqtt[forecast]
   ```

3. **Configuration**: 
   - Create a `config/` directory
   - Download [configuration.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/config/configuration.yml.example) and save as `config/configuration.yml`
   - Download [secrets.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/config/secrets.yml.example) and save as `config/secrets.yml`
   - Edit both files with your specific settings

4. **Execution**: Run `solaredge2mqtt` in your terminal

**Migration from older versions**: If you have an existing `.env` file, the service will automatically create YAML configuration files in the `config/` directory on first run.

### With Docker

Docker provides an isolated deployment approach:

1. **Pull the Image**: 
   ```bash
   docker pull ghcr.io/deroetzi/solaredge2mqtt:latest
   ```

2. **Running with YAML configuration** (recommended):
   ```bash
   docker run --name solaredge2mqtt --rm \
       -v $(pwd)/config:/app/config \
       -e "TZ=Europe/Berlin" \
       ghcr.io/deroetzi/solaredge2mqtt:latest
   ```

3. **Running with environment variables** (automatic migration):
   ```bash
   docker run --name solaredge2mqtt --rm \
       -v $(pwd)/config:/app/config \
       -e "SE2MQTT_MODBUS__HOST=<INVERTER_IP>" \
       -e "SE2MQTT_MQTT__BROKER=<BROKER_IP>" \
       -e "SE2MQTT_MQTT__PASSWORD=<PASSWORD>" \
       -e "TZ=Europe/Berlin" \
       ghcr.io/deroetzi/solaredge2mqtt:latest
   ```
   
   On first run, the service will create `config/configuration.yml` and `config/secrets.yml` files automatically.

### With Docker Compose

For multi-container deployments:

1. **Configuration**: Download the example files:
   - [docker-compose.yml](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml)
   - [configuration.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/config/configuration.yml.example)
   - [secrets.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/config/secrets.yml.example)

2. **Setup**: 
   - Create a `config/` directory
   - Save `configuration.yml.example` as `config/configuration.yml`
   - Save `secrets.yml.example` as `config/secrets.yml`
   - Edit both files with your settings

3. **Execution**: 
   ```bash
   docker compose up -d
   ```

4. **View Logs**: 
   ```bash
   docker logs solaredge2mqtt -f
   ```

5. **Stop Service**: 
   ```bash
   docker compose down
   ```

**Migration Note**: If you're upgrading from an older version with `.env` configuration, you can either:
- Use the manual migration tool: `docker run --rm -v $(pwd)/config:/app/config ghcr.io/deroetzi/solaredge2mqtt:latest solaredge2mqtt-migrate --input .env --output-dir config`
- Let the service auto-migrate on first run (it will detect the `.env` file and create YAML configurations in `config/`)

[buymecoffee-link]: https://www.buymeacoffee.com/deroetzik
[buymecoffee-shield]: https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png
