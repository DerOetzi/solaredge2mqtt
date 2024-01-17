# SolarEdge 2 MQTT Service
[![License](https://img.shields.io/github/license/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/blob/main/LICENSE) [![Release](https://img.shields.io/github/v/release/DerOetzi/solaredge2mqtt)](https://github.com/DerOetzi/solaredge2mqtt/releases/latest) [![Build Status](https://img.shields.io/github/actions/workflow/status/DerOetzi/solaredge2mqtt/build_project.yml?branch=main)](https://github.com/DerOetzi/solaredge2mqtt/actions/workflows/build_project.yml) [![PyPI version](https://img.shields.io/pypi/v/solaredge2mqtt.svg)](https://pypi.org/project/solaredge2mqtt/) [![Discord Chat](https://img.shields.io/discord/1196540254686032014)](https://discord.gg/QXfghc93pY)

The SolarEdge2MQTT service is a project designed to read power data from a SolarEdge inverter and publish it to an MQTT broker. The service is useful for integrating SolarEdge inverters into home automation systems or other applications that use MQTT for data exchange. It provides real-time monitoring of power flow and other parameters from the inverter via Modbus. 

You can also gather the panels' energy production data from the SolarEdge monitoring site. This feature is optional and does not use the API, but rather your monitoring platform account.

The SolarEdge Wallbox can be monitored as well via REST API.

Additionally all values can be saved for visualization into a InfluxDB.

*The SolarEdge2MQTT service is currently in an early stage of development. While it is functional and can be used to read data from a SolarEdge inverter and publish it to an MQTT broker, it is still undergoing active development. Features may be added, removed, or changed, and there may be bugs. Users should be aware of this and use the service with caution. Despite its early state, the project is open-source and contributions are welcome.*


## Contact and Feedback

If you have any questions, please contact me on Discord.

[![Discord Banner](https://discordapp.com/api/guilds/1196540254686032014/widget.png?style=banner2)](https://discord.gg/QXfghc93pY)

Please share your ideas, suggestions or problems by opening an [issue](https://github.com/DerOetzi/solaredge2mqtt/issues). I am really looking forward to your feedback.

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

#### Basic configuration

Environment Variable             | default  | description                                            
-------------------------------- | -------- | ------------------------------------------------------ 
SE2MQTT_INTERVAL                 | 5        | Interval between requests in seconds
SE2MQTT_LOGGING_LEVEL            | INFO     | Set logging level to DEBUG, INFO, WARNING, ERROR, CRITICAL

#### Modbus configuration

Environment Variable             | default  | description                                            
-------------------------------- | -------- | ------------------------------------------------------ 
SE2MQTT_MODBUS__HOST             | *None*   | IP address of your inverter
SE2MQTT_MODBUS__PORT             | 1502     | Modbus port of your inverter
SE2MQTT_MODBUS__TIMEOUT          | 1        | Timeout for the modbus connection
SE2MQTT_MODBUS__UNIT             | 1        | Modbus unit address

#### MQTT configuration

Environment Variable             | default        | description                                            
-------------------------------- | ---------------| ------------------------------------------------------ 
SE2MQTT_MQTT__CLIENT_ID          | solaredge2mqtt | MQTT client id
SE2MQTT_MQTT__BROKER             | *None*         | IP address of your MQTT broker
SE2MQTT_MQTT__PORT               | 1883           | Port of your MQTT broker
SE2MQTT_MQTT__USERNAME           | *None*         | Username to authenticate to your MQTT broker
SE2MQTT_MQTT__PASSWORD           | *None*         | Password to authenticate to your MQTT broker (for security reason use secrets with docker)
SE2MQTT_MQTT__TOPIC_PREFIX       | solaredge      | SolarEdge2MQTT will use this as prefix topic

#### Monitoring

If you want to get panel energy values from the SolarEdge monitoring platform, add additional parameters.

Environment Variable             | description                                            
-------------------------------- | ------------------------------------------------------ 
SE2MQTT_MONITORING__SITE_ID      | Your site id from the SolarEdge monitoring plattform
SE2MQTT_MONITORING__USERNAME     | Your username for your account on the SolarEdge monitoring platform
SE2MQTT_MONITORING__PASSWORD     | Your password for your account on the SolarEdge monitoring plattform (for security reason use secrets with docker)

If you want to monitor the power values of your SolarEdge Wallbox, add additional parameters. The Wallbox needs to have firmware version >= 1.15.0 and activated REST API. 

#### Wallbox

Environment Variable      | description                                            
--------------------------| ------------------------------------------------------ 
SE2MQTT_WALLBOX__HOST     | The IP adress of your wallbox
SE2MQTT_WALLBOX__PASSWORD | The password of user `admin` you use to login the Web UI of your Wallbox
SE2MQTT_WALLBOX__SERIAL   | The serial number of your wallbox

#### InfluxDB

If you want to save the monitoring data to a InfluxDB you have to generate a full access token, because the service will generate two buckets and a task for you.

The first bucket (raw) is used to store every interval the data of the components `inverter`, `meters`, `batteries` and `wallbox` to a measurement called `component` and the current `powerflow` state. This can be useful for debugging reasons. The generated aggregation task will store the `energy` values of every minute to this bucket. By default this bucket holds the values for 24h.

The second bucket is used by the aggregation task to store the `powerflow` states and `energy` values aggregated by 1 hour intervals. By default this bucket holds the values for 2 years.

Environment Variable                   | default                | description                                            
-------------------------------------- | ---------------------- | ------------------------------------------------------ 
SE2MQTT_INFLUXDB__HOST                 | *None*                 | Set your host (for example: http://localhost)
SE2MQTT_INFLUXDB__PORT                 | 8086                   | Set your port
SE2MQTT_INFLUXDB__TOKEN                | *None*                 | Set your token (for security reasons use a secret with docker) The token must have full access because the service manages the needed buckets and tasks
SE2MQTT_INFLUXDB__ORG                  | *None*                 | Set your organization ID
SE2MQTT_INFLUXDB__PREFIX               | solaredge/solaredgedev | Set a prefix for bucket and task names
SE2MQTT_INFLUXDB__RETENTION_RAW        | 90000 = 25h            | Set a retention policy in seconds for bucket raw
SE2MQTT_INFLUXDB__RETENTION_AGGREGATED | 63072000 = 2 years     | Set a retention policy in seconds for bucket aggegrated
SE2MQTT_INFLUXDB__AGGREGATED_INTERVAL  | 10m                    | Aggregate power and energy valuse in InfluxDB  set a interval for the task should be between 10m and 1h


#### Example configuration

You can download [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/.env.example) and rename it to `.env`. Inside, you can modify the default configuration values to meet your needs in this file.

## Run the service 

### In the console

Copy the [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/.env.example) file to .env and modify it according to your needs.

Then, simply run `solaredge2mqtt` to start the service.

### With docker:

```
docker run --name solaredge2mqtt --rm \
    -e "SE2MQTT_MODBUS__HOST=<INVERTER_IP>" \
    -e "SE2MQTT_MQTT__BROKER=<BROKER_IP>" \
    -e "SE2MQTT_MQTT__USERNAME=<MQTT_USERNAME>" \
    -e "SE2MQTT_MQTT__PASSWORD=<MQTT_PASSWORD>" \
    -e "TZ=Europe/Berlin" \
    ghcr.io/deroetzi/solaredge2mqtt:latest
```

Add optional environment arguments from above to fit to your setup.

### With docker-compose

Copy the [.env.example](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/.env.example) file to `.env` and modify it according to your needs.

Get the [docker-compose.yml](https://raw.githubusercontent.com/DerOetzi/solaredge2mqtt/master/docker-compose.yml) file.

Generate a `.secrets` directory and put at least a file called `mqtt_password` inside with your MQTT broker password.

If you want to use module energy values additionally, uncomment the secrets parts for the `se2mqtt_monitoring__password` secret inside the `docker-compose.yml` file and place an `monitoring_password` file in the `.secrets` directory. The same applies to `wallbox_password` and `influxdb_token`. These are the minimum secrets you should use. Feel free to extend it with other parameters such as usernames, site_id, and location. 

Read more about docker secrets here: https://docs.docker.com/engine/swarm/secrets/

Run the docker container

```
docker-compose up -d
```

Stop the docker container

```
docker-compose down
```