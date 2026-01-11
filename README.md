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

SolarEdge2MQTT uses YAML-based configuration files for easy and structured setup. Configuration is stored in two files:

- **`configuration.yml`**: Contains all non-sensitive settings
- **`secrets.yml`**: Contains sensitive data (passwords, tokens, API keys)

### Quick Start

For new installations, the service will automatically create example configuration files on first run if they don't exist. Simply start the service and it will guide you through the setup process.

### Configuration Files

You can download example configuration files to get started:
- [configuration.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example)
- [secrets.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example)

**Setup steps:**
1. Create a `config/` directory (or use `--config-dir` to specify a different location)
2. Copy the example files and rename them to `configuration.yml` and `secrets.yml`
3. Edit both files with your specific settings

### Configurable Configuration Directory

By default, SolarEdge2MQTT looks for configuration files in the `config/` directory. You can specify a different location using the `--config-dir` argument:

```bash
# Use default config directory (./config/)
solaredge2mqtt

# Use custom config directory
solaredge2mqtt --config-dir /etc/solaredge2mqtt

# Show help
solaredge2mqtt --help
```

### Migration from Environment Variables

**⚠️ Breaking Change**: Starting with version 2.0.0, SolarEdge2MQTT uses YAML configuration files instead of environment variables.

If you're upgrading from a previous version that used environment variables, `.env` files, or Docker secrets, SolarEdge2MQTT provides an automatic and manual migration path.

#### Automatic Migration

When you start the service for the first time after upgrading, if no YAML configuration files exist (or they're empty), the service will:

1. **Check for environment variables** from:
   - Current environment variables
   - `.env` file (if present)
   - Docker secrets in `/run/secrets/` (if present)

2. **If environment variables are found**:
   - Automatically create `configuration.yml` and `secrets.yml` in your config directory
   - Separate sensitive values into `secrets.yml`
   - Use `!secret` tags in `configuration.yml` to reference secrets
   - The service will then start normally with your migrated configuration

3. **If no environment variables are found** (new installation):
   - Copy example files to your config directory
   - Exit with a helpful message asking you to configure the files
   - Start the service again after editing the configuration

#### Manual Migration

For more control over the migration process, use the migration CLI tool:

```bash
# Migrate from .env file to config directory
solaredge2mqtt-migrate --input .env --output-dir config

# Preview changes without writing files
solaredge2mqtt-migrate --input .env --output-dir config --dry-run

# Create backups of existing files before migration
solaredge2mqtt-migrate --input .env --output-dir config --backup
```

**Migration options:**
- `--input PATH`: Path to .env file (default: `.env`)
- `--output-dir PATH`: Output directory for YAML files (default: `config`)
- `--dry-run`: Preview changes without writing files
- `--backup`: Create timestamped backups of existing configuration files

#### Docker Migration

For Docker users migrating from environment variables:

**Option 1: Use the migration tool**
```bash
# Run migration tool in a container
docker run --rm -v $(pwd)/config:/app/config \
    ghcr.io/deroetzi/solaredge2mqtt:latest \
    solaredge2mqtt-migrate --input .env --output-dir config --backup
```

**Option 2: Let the service auto-migrate**
1. Mount the config volume: `-v $(pwd)/config:/app/config`
2. Keep your environment variables or `.env` file for the first run
3. Start the container - it will automatically create YAML files
4. After successful migration, remove the environment variables from your docker-compose.yml or docker run command
5. Restart the container - it will now use the YAML configuration

#### Environment Variable Mapping

Environment variables are converted to YAML structure using double underscores (`__`) as separators:

```bash
# Environment variable format
SE2MQTT_MODBUS__HOST=192.168.1.100
SE2MQTT_MQTT__BROKER=mqtt.example.com
SE2MQTT_MQTT__PASSWORD=secret123

# Converts to YAML
modbus:
  host: 192.168.1.100
mqtt:
  broker: mqtt.example.com
  password: !secret mqtt_password  # Automatically moved to secrets.yml

# And secrets.yml
mqtt_password: "secret123"
```

#### Post-Migration

After successful migration:
1. **Verify** the generated `configuration.yml` and `secrets.yml` files
2. **Test** that the service starts correctly with the new configuration
3. **Remove** old environment variables, `.env` files, or Docker secrets
4. **Backup** your new YAML configuration files

### Secret References

To keep sensitive data secure, use the `!secret` tag in your configuration. This tag references values stored in `secrets.yml`:

```yaml
# configuration.yml
mqtt:
  broker: mqtt.example.com
  password: !secret mqtt_password

# secrets.yml
mqtt_password: "your_actual_password"
```

**Benefits of using secrets.yml:**
- Sensitive data is separated from main configuration
- `secrets.yml` is automatically created with restrictive 600 permissions
- Easy to exclude from version control
- Can be managed separately in deployment pipelines

The migration tool automatically identifies sensitive fields (passwords, tokens, API keys, serial numbers, site IDs) and moves them to `secrets.yml`.

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
   - Create a `config/` directory (or use a custom location with `--config-dir`)
   - Download [configuration.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example) and save as `config/configuration.yml`
   - Download [secrets.yml.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example) and save as `config/secrets.yml`
   - Edit both files with your specific settings

4. **Execution**: 
   ```bash
   # Use default config directory (./config/)
   solaredge2mqtt
   
   # Use custom config directory
   solaredge2mqtt --config-dir /path/to/config
   ```

**New Installation Flow**: On first run without configuration files, the service will automatically copy example files to your config directory and exit with instructions. Edit the files and run again.

**Migration from older versions**: If you have an existing `.env` file, the service will automatically create YAML configuration files in the `config/` directory on first run. See the [Migration section](#migration-from-environment-variables) for details.

### With Docker

Docker provides an isolated deployment approach with persistent configuration storage:

1. **Pull the Image**: 
   ```bash
   docker pull ghcr.io/deroetzi/solaredge2mqtt:latest
   ```

2. **Prepare Configuration Directory**:
   ```bash
   mkdir -p config
   ```

3. **Running with YAML configuration** (recommended):
   
   **First time setup:**
   ```bash
   # Download example files
   curl -o config/configuration.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
   curl -o config/secrets.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example
   
   # Edit the files with your settings
   nano config/configuration.yml
   nano config/secrets.yml
   
   # Run the container
   docker run -d --name solaredge2mqtt \
       -v $(pwd)/config:/app/config \
       -e "TZ=Europe/Berlin" \
       --restart unless-stopped \
       ghcr.io/deroetzi/solaredge2mqtt:latest
   ```
   
   **Alternative - Auto-setup on first run:**
   ```bash
   # Run without configuration files
   docker run -d --name solaredge2mqtt \
       -v $(pwd)/config:/app/config \
       -e "TZ=Europe/Berlin" \
       --restart unless-stopped \
       ghcr.io/deroetzi/solaredge2mqtt:latest
   
   # The service will create example files in config/ and exit
   # Edit the files, then restart:
   docker restart solaredge2mqtt
   ```

4. **Migrating from environment variables**:
   
   If you're upgrading from an older version that used environment variables:
   
   ```bash
   # Option 1: Auto-migrate on first run
   docker run -d --name solaredge2mqtt \
       -v $(pwd)/config:/app/config \
       -e "SE2MQTT_MODBUS__HOST=<INVERTER_IP>" \
       -e "SE2MQTT_MQTT__BROKER=<BROKER_IP>" \
       -e "SE2MQTT_MQTT__PASSWORD=<PASSWORD>" \
       -e "TZ=Europe/Berlin" \
       --restart unless-stopped \
       ghcr.io/deroetzi/solaredge2mqtt:latest
   ```
   
   The service will detect environment variables and create YAML files automatically in `config/`. After verifying the migration, restart without the environment variables:
   
   ```bash
   docker stop solaredge2mqtt
   docker rm solaredge2mqtt
   docker run -d --name solaredge2mqtt \
       -v $(pwd)/config:/app/config \
       -e "TZ=Europe/Berlin" \
       --restart unless-stopped \
       ghcr.io/deroetzi/solaredge2mqtt:latest
   ```
   
   ```bash
   # Option 2: Use migration tool
   docker run --rm \
       -v $(pwd)/config:/app/config \
       -v $(pwd)/.env:/app/.env:ro \
       ghcr.io/deroetzi/solaredge2mqtt:latest \
       solaredge2mqtt-migrate --input .env --output-dir config --backup
   ```

5. **View Logs**:
   ```bash
   docker logs solaredge2mqtt -f
   ```

6. **Stop Service**:
   ```bash
   docker stop solaredge2mqtt
   docker rm solaredge2mqtt
   ```

### With Docker Compose

For multi-container deployments with persistent configuration:

1. **Download Files**: Get the docker-compose.yml and example configuration files:
   ```bash
   # Download docker-compose.yml
   curl -o docker-compose.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml
   
   # Create config directory and download examples
   mkdir -p config
   curl -o config/configuration.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/configuration.yml.example
   curl -o config/secrets.yml https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/solaredge2mqtt/config/secrets.yml.example
   ```

2. **Configure**: Edit your configuration files:
   ```bash
   nano config/configuration.yml
   nano config/secrets.yml
   ```

3. **Start Service**: 
   ```bash
   docker compose up -d
   ```

4. **View Logs**: 
   ```bash
   docker compose logs solaredge2mqtt -f
   ```

5. **Stop Service**: 
   ```bash
   docker compose down
   ```

**New Installation**: The `docker-compose.yml` file now uses a volume mount for the config directory (`./config:/app/config`). On first run without configuration files, the service will create example files and exit. Edit them and restart with `docker compose up -d`.

**Migration from older versions**: 

If you're upgrading from an older version that used `.env` files or environment variables:

- **Automatic Migration**: Keep your `.env` file or environment variables in `docker-compose.yml` for the first run. The service will detect them and create YAML configuration files in the `config/` directory. After verifying the migration works, remove the environment variables from `docker-compose.yml` and restart.

- **Manual Migration**: Use the migration tool before starting:
  ```bash
  docker compose run --rm solaredge2mqtt solaredge2mqtt-migrate --input .env --output-dir config --backup
  docker compose up -d
  ```

**Full-Stack Example**: For a complete deployment with InfluxDB and Grafana, see [examples/docker-compose-full-stack.yaml](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/examples/docker-compose-full-stack.yaml)

[buymecoffee-link]: https://www.buymeacoffee.com/deroetzik
[buymecoffee-shield]: https://www.buymeacoffee.com/assets/img/custom_images/yellow_img.png
