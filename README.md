# SolarEdge 2 MQTT Service
[![License](https://img.shields.io/github/license/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/blob/main/LICENSE) [![Release](https://img.shields.io/github/v/release/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/releases/latest) [![Build Status](https://img.shields.io/github/actions/workflow/status/DerOetzi/solaredge2mqtt/build_project.yml?branch=main)](https://github.com/DerOetzi/solaredge2mqtt/actions/workflows/build_project.yml) [![PyPI version](https://img.shields.io/pypi/v/solaredge2mqtt.svg)](https://pypi.org/project/solaredge2mqtt/) 

The SolarEdge2MQTT service is a project designed to read data from a SolarEdge inverter and publish it to an MQTT broker. The service is useful for integrating SolarEdge inverters into home automation systems or other applications that use MQTT for data exchange. It provides real-time monitoring of power flow and other parameters from the inverter via Modbus. 

You can also gather the panels' energy production data from the SolarEdge monitoring site. This feature is optional and does not use the API, but rather your monitoring platform account.

*The SolarEdge2MQTT service is currently in an early stage of development. While it is functional and can be used to read data from a SolarEdge inverter and publish it to an MQTT broker, it is still undergoing active development. Features may be added, removed, or changed, and there may be bugs. Users should be aware of this and use the service with caution. Despite its early state, the project is open-source and contributions are welcome.*

## Installation and Configuration

Install and update using pip.
```
pip install -U solaredge2mqtt
```

Install and update using docker
```
docker pull ghcr.io/deroetzi/solaredge2mqtt:latest
```

### Service configuration

The service is configured by environment variables. The following options can be set:

Environment Variable             | default (production/development) | description                                            
-------------------------------- | -------------------------------- | ------------------------------------------------------ 
SE2MQTT_ENVIRONMENT              | production                       | Choose the default environment settings: production or development. 
SE2MQTT_MODBUS_HOST              | *None*                           | IP address of your inverter
SE2MQTT_MODBUS_PORT              | 1502                             | Modbus port of your inverter
SE2MQTT_MODBUS_TIMEOUT           | 1                                | Timeout for the modbus connection
SE2MQTT_MODBUS_UNIT              | 1                                | Modbus unit address
SE2MQTT_CLIENT_ID                | solaredge2mqtt                   | MQTT client id
SE2MQTT_BROKER                   | *None*                           | IP address of your MQTT broker
SE2MQTT_PORT                     | 1883                             | Port of your MQTT broker
SE2MQTT_USERNAME                 | *None*                           | Username to authenticate to your MQTT broker
SE2MQTT_PASSWORD                 | *None*                           | Password to authenticate to your MQTT broker (for security reason use secrets with docker)
SE2MQTT_TOPIC_PREFIX             | solaredge                        | SolarEdge2MQTT will use this as prefix topic
SE2MQTT_INTERVAL                 | 5                                | Interval between requests in seconds
SE2MQTT_LOGGING_LEVEL            | INFO                             | Set logging level to DEBUG, INFO, WARNING, ERROR, CRITICAL

If you want to get panel energy values from the SolarEdge monitoring platform, add additional parameters.

Environment Variable             | description                                            
-------------------------------- | ------------------------------------------------------ 
SE2MQTT_API_SITE_ID              | Your site id from the SolarEdge monitoring plattform
SE2MQTT_API_USERNAME             | Your username for your account on the SolarEdge monitoring platform
SE2MQTT_API_PASSWORD             | Your password for your account on the SolarEdge monitoring plattform (for security reason use secrets with docker)


#### Example configuration

You can download [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/core/.env.example) and rename it to `.env`. Inside, you can modify the default configuration values to meet your needs in this file.

## Run the service 

### In the console

Copy the [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/core/.env.example) file to .env and modify it according to your needs.

Then, simply run `solaredge2mqtt` to start the service.

### With docker:

```
docker run --name solaredge2mqtt --rm \
    -e "SE2MQTT_MODBUS_HOST=<INVERTER_IP>" \
    -e "SE2MQTT_BROKER=<BROKER_IP>" \
    -e "SE2MQTT_USERNAME=<MQTT_USERNAME>" \
    -e "SE2MQTT_PASSWORD=<MQTT_PASSWORD>" \
    -e "TZ=Europe/Berlin" \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

Add optional environment arguments from above to fit to your setup.

### With docker-compose

Copy the [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/core/.env.example) file to `.env` and modify it according to your needs.

Get the [docker-compose.yml](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/core/docker/docker-compose.yml) file.

Generate a `.secrets` directory and put at least a file called `mqtt_password` inside with your MQTT broker password.

If you want to use module energy values additionally, uncomment the secrets parts for the `se2mqtt_api_password` secret inside the `docker-compose.yml`` and put a `api_password` file in the `.secrets` directory as well.

Run the docker container

```
docker-compose up -d
```

Stop the docker container

```
docker-compose down
```