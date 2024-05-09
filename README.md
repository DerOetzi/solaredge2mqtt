# SolarEdge 2 MQTT Service

[![License](https://img.shields.io/github/license/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/blob/main/LICENSE) [![Release](https://img.shields.io/github/v/release/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/releases/latest) [![Build Status](https://img.shields.io/github/actions/workflow/status/DerOetzi/solaredge2mqtt/build_project.yml?branch=main)](https://github.com/DerOetzi/solaredge2mqtt/actions/workflows/build_project.yml) [![PyPI version](https://img.shields.io/pypi/v/solaredge2mqtt.svg)](https://pypi.org/project/solaredge2mqtt/) [![Discord Chat](https://img.shields.io/discord/1196540254686032014)](https://discord.gg/QXfghc93pY)

The SolarEdge2MQTT service facilitates the retrieval of power data from SolarEdge inverters and its publication to an MQTT broker. Ideal for integrating SolarEdge inverters into home automation systems, this service supports real-time monitoring of power flow and additional parameters via Modbus.

Users can optionally collect panel energy production data directly from the SolarEdge monitoring site, without employing the API, by leveraging their monitoring platform account.

It also enables the monitoring of SolarEdge Wallbox via the REST API and supports saving all values into InfluxDB for advanced visualization.

_Please note: The SolarEdge2MQTT service is in its early development stages. Although operational for reading and publishing data from a SolarEdge inverter, active development may introduce changes to features, potential removals, or bugs. Users are advised to proceed with caution. As an open-source project, contributions are highly encouraged._

## Contact and Feedback

For inquiries, feel free to reach out on Discord.

[![Discord Banner](https://discordapp.com/api/guilds/1196540254686032014/widget.png?style=banner2)](https://discord.gg/QXfghc93pY)

We highly value your input. Share your ideas, suggestions, or issues by opening an [issue](https://github.com/DerOetzi/solaredge2mqtt/issues). Your feedback is eagerly awaited.

## Configuration

You can download [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/.env.example) and rename it to `.env`. Inside, you can modify the default configuration values to meet your needs in this file.

Configure the service using environment variables. The available options are listed below for customization:

### Basic configuration

- **SE2MQTT_INTERVAL**: The frequency (in seconds) of data retrieval requests. Default is every 5 seconds.
- **SE2MQTT_LOGGING_LEVEL**: Adjust the verbosity of logs. Options include DEBUG, INFO, WARNING, ERROR, and CRITICAL.
- **SE2MQTT_LOCATION\_\_LATITUDE** and **SE2MQTT_LOCATION\_\_LONGITUDE**: Specify your location to enable weather and forecast services. These settings are essential for accurate environmental data and PV production forecasts.

### Modbus configuration

- **SE2MQTT_MODBUS\_\_HOST**: The IP address of your SolarEdge inverter.
- **SE2MQTT_MODBUS\_\_PORT**: The port on which your inverter's Modbus is accessible. Default is 1502.
- **SE2MQTT_MODBUS\_\_TIMEOUT**: The timeout (in seconds) for Modbus connections. A lower value makes the system more responsive but may lead to incomplete data in environments with poor network conditions.
- **SE2MQTT_MODBUS\_\_UNIT**: The unit address for Modbus communication. Default is 1.

### MQTT configuration

- **SE2MQTT_MQTT\_\_CLIENT_ID**: Identifier for the MQTT client, defaults to 'solaredge2mqtt'.
- **SE2MQTT_MQTT\_\_BROKER**: The IP address of your MQTT broker.
- **SE2MQTT_MQTT\_\_PORT**: The port your MQTT broker listens on. Default is 1883.
- **SE2MQTT_MQTT\_\_USERNAME** and **SE2MQTT_MQTT\_\_PASSWORD**: Credentials for connecting to your MQTT broker. It's recommended to use secrets for the password if deploying with Docker.
- **SE2MQTT_MQTT\_\_TOPIC_PREFIX**: The prefix used for MQTT topics. Defaults to 'solaredge'.

### Monitoring

To enable panel energy value retrieval from the SolarEdge monitoring platform, you must configure:

- **SE2MQTT_MONITORING\_\_SITE_ID**: Your site ID as registered on the SolarEdge platform.
- **SE2MQTT_MONITORING\_\_USERNAME**: Your username for the SolarEdge monitoring platform.
- **SE2MQTT_MONITORING\_\_PASSWORD**: Your password. Ensure to use Docker secrets or a secure method to protect this information.

### Wallbox

For monitoring SolarEdge Wallbox, provide:

- **SE2MQTT_WALLBOX\_\_HOST**: The IP address of your Wallbox.
- **SE2MQTT_WALLBOX\_\_PASSWORD**: The admin password for Wallbox web UI access.
- **SE2MQTT_WALLBOX\_\_SERIAL**: The serial number of your Wallbox.

### Home Assistant Auto Discovery

If you want Home Assistant to auto discover the data SolarEdge2MQTT provides, you can enable this here.

- **SE2MQTT_HOMEASSISTANT\_\_ENABLE**: Set to true to enable the auto discovery
- **SE2MQTT_HOMEASSISTANT\_\_TOPIC_PREFIX**: By default Home Assistant MQTT integration listens to subtopics of homeassistant

_If you want to remove things, just disable the feature, then restart SolarEdge2MQTT first and after it restart Home Assistant,_

### InfluxDB

Configure your InfluxDB settings with these environment variables to store monitoring data effectively:

- **SE2MQTT_INFLUXDB\_\_HOST**: Specify the host of your InfluxDB instance (e.g., http://localhost). Default is None.
- **SE2MQTT_INFLUXDB\_\_PORT**: The port number on which your InfluxDB instance is running. The default value is 8086.
- **SE2MQTT_INFLUXDB\_\_TOKEN**: Your access token for InfluxDB. It is imperative to use this token securely, especially when deploying with Docker. The token requires full access since the service will be managing necessary buckets and tasks. Default is None.
- **SE2MQTT_INFLUXDB\_\_ORG**: The ID of your organization within InfluxDB. Default is None.
- **SE2MQTT_INFLUXDB\_\_BUCKET**: The name of the bucket where the data will be saved. Default bucket name is solaredge.
- **SE2MQTT_INFLUXDB\_\_RETENTION_RAW**: The retention policy for raw data in hours. This setting defines how long the raw power values are stored in InfluxDB. Default is 25 hours.
- **SE2MQTT_INFLUXDB\_\_RETENTION**: The retention policy for aggregated data in seconds. This sets how long the aggregated data will be stored in InfluxDB, with the default being 2 years (63072000 seconds).
  These configurations allow you to tailor the InfluxDB storage for your SolarEdge monitoring data, ensuring that you have the flexibility to define how long the data should be retained both in raw and aggregated forms.

### Price Configuration

To calculate your savings and earnings, you can specify the amount you pay for consumption and the amount you receive for delivery per kilowatt-hour (kWh). Please note, this feature is only operational in conjunction with InfluxDB.

- **SE2MQTT_PRICES\_\_CONSUMPTION**: Set the price you pay per 1 kWh for energy received from the grid.
- **SE2MQTT_PRICES\_\_DELIVERY**: Set the price you receive per 1 kWh for energy delivered to the grid.

These additional settings allow for a comprehensive analysis of your energy production and usage, enabling you not just to monitor energy flow but also understand the financial aspects of your energy generation and consumption.

### Weather

Leverage real-time weather data in your SolarEdge2MQTT service by integrating with OpenWeatherMap. This feature enriches your service with accurate environmental conditions, which can be essential for detailed energy production analysis.

- **SE2MQTT_WEATHER\_\_API_KEY**: Securely set your OpenWeatherMap OneCall API key here. For enhanced security, it's recommended to use this key as a secret within Docker environments.
- **SE2MQTT_WEATHER\_\_LANGUAGE**: Customize the language for weather data retrieved from the API. The default setting is English (en).

To access current weather data, ensure you have an OpenWeatherMap account, an API key, and a [subscription](https://home.openweathermap.org/subscriptions) to the One-Call API. Visit [OpenWeatherMap](https://openweathermap.org/) for more information on obtaining these prerequisites.

### Forecast

The SolarEdge2MQTT service features an integrated machine learning component designed to forecast PV production for the current and following day. For optimal functionality, confirm that your settings for [location](https://github.com/DerOetzi/solaredge2mqtt/blob/main/README.md#basic-configuration), [InfluxDB](https://github.com/DerOetzi/solaredge2mqtt/blob/main/README.md#influxdb) and [weather](https://github.com/DerOetzi/solaredge2mqtt/blob/main/README.md#weather) are correctly configured.

- **SE2MQTT_FORECAST\_\_ENABLE**: Activate the machine learning-based forecast feature by setting this to true. The default is false.
- **SE2MQTT_FORECAST\_\_HYPERPARAMETERTUNING**: Optimize forecast accuracy by enabling hyperparameter tuning. Note that this process is computationally intensive and may not be suitable for devices with limited processing power, such as Raspberry Pi. The default setting is false.

**Precondition for Forecasting**: Before a forecast can be made, a minimum of 60 hours of training data must be collected. These data serve as the basis for model training and are crucial for prediction accuracy. Ensure that the service has had sufficient time to collect data before expecting forecast activation.

**Note on Training Data Collection**: If the service goes without recording production data for longer than an hour, it will be unable to save training data. It's essential to ensure consistent data recording to maintain the integrity of the training process and ensure accurate forecasting.

_Your experience and feedback, especially regarding forecast accuracy and performance on low-powered devices, are highly valued. This continuous improvement effort aims to enhance the predictive capabilities of the SolarEdge2MQTT service for all users._

## Running the service

Each of these methods provides a different level of control and isolation, catering to various use cases from development and testing to full-scale production deployment.

### In the Console

For users looking to run SolarEdge2MQTT directly within their console, which is ideal for testing or development environments, follow these steps:

1. **Preparation**: Ensure you have Python installed on your system. The service is compatible with Python >=3.10.
2. **Installation**: If you haven't already, install the service using pip with the command `pip install -U solaredge2mqtt`. This command fetches the latest version and installs all necessary dependencies.
3. **Environment Configuration**: Copy the [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/.env.example) file to a new file named `.env`. Open this file in a text editor and adjust the environment variables to match your system and preferences. This includes setting up your MQTT broker, InfluxDB credentials, and any other service configurations as detailed in the README.
4. **Execution**: With your environment configured, run the command solaredge2mqtt in your terminal. The service will start and begin operating based on the settings you've specified in the .env file.

### With Docker

Docker offers a more isolated and scalable approach to deploying the SolarEdge2MQTT service. To run the service using Docker:

1. **Docker Installation**: Ensure Docker is installed and running on your system. Docker is available for various operating systems and provides detailed installation guides on its website.
2. **Pulling the Docker Image**: Execute the command `docker pull ghcr.io/deroetzi/solaredge2mqtt:latest` to download the latest Docker image of the service.
3. **Running the Container**: Use the docker run command to start the service. Include environment variable flags (-e) for each configuration option you need to specify. For example:

```
docker run --name solaredge2mqtt --rm \
    -e "SE2MQTT_MODBUS__HOST=<INVERTER_IP>" \
    -e "SE2MQTT_MQTT__BROKER=<BROKER_IP>" \
    -e "TZ=Europe/Berlin" \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

Replace <INVERTER_IP> and <BROKER_IP> with your specific values. Add any additional environment variables as needed.

### With Docker Compose

For a more advanced deployment, especially when integrating with other services like MQTT brokers or InfluxDB, Docker Compose facilitates managing multi-container Docker applications:

1. **Docker Compose Installation**: Ensure Docker Compose is installed on your system. It's typically included with Docker Desktop for Windows and Mac but may require separate installation on Linux.
2. **Configuration**: Obtain the [docker-compose.yml](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml) file from the SolarEdge2MQTT GitHub repository. Edit this file to include your specific environment variables and any other services you wish to integrate.
3. **Environment File**: Similar to running in the console, copy the [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/.env.example) file to `.env` and adjust the settings to fit your setup.
4. **Execution**: Run `docker-compose up -d` to start the service in detached mode. This command reads your `docker-compose.yml` and `.env` file, setting up your SolarEdge2MQTT service along with any other specified services.

Stopping the Service: When you need to stop the service, use `docker-compose down` to gracefully stop and remove the containers defined in your Docker Compose file.
