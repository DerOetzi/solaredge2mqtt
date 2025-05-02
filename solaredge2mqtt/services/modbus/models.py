from __future__ import annotations

from influxdb_client import Point
from pydantic import Field

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.homeassistant.models import \
    HomeAssistantBinarySensorType as HABinarySensor
from solaredge2mqtt.services.homeassistant.models import \
    HomeAssistantNumberType as HANumber
from solaredge2mqtt.services.homeassistant.models import \
    HomeAssistantSensorType as HASensor
from solaredge2mqtt.services.modbus.sunspec.values import (BATTERY_STATUS_MAP,
                                                           C_SUNSPEC_DID_MAP,
                                                           INVERTER_STATUS_MAP)
from solaredge2mqtt.services.models import Component, ComponentValueGroup
















