from typing import Any

from influxdb_client.client.write.point import Point
from pydantic import Field

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.base import ModbusComponent
from solaredge2mqtt.services.modbus.sunspec.values import (
    BATTERY_STATUS_MAP,
    SunSpecPayload,
)


class ModbusBattery(ModbusComponent):
    COMPONENT = "battery"

    status: int = Field(**HASensor.STATUS.field("Status"))
    status_text: str = Field(**HASensor.STATUS.field("Status text"))
    current: float = Field(**HASensor.CURRENT_A.field("current"))
    voltage: float = Field(**HASensor.VOLTAGE_V.field("voltage"))
    power: float = Field(**HASensor.POWER_W.field("power"))
    state_of_charge: float = Field(**HASensor.BATTERY.field("state of charge"))
    state_of_health: float = Field(**HASensor.BATTERY.field("state of health"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        values = {
            "status": int(payload["status"]),
            "current": round(float(payload["instantaneous_current"]), 2),
            "voltage": round(float(payload["instantaneous_voltage"]), 2),
            "power": round(float(payload["instantaneous_power"]), 2),
            "state_of_charge": round(float(payload["soe"]), 2),
            "state_of_health": round(float(payload["soh"]), 2),
        }

        if values["status"] in BATTERY_STATUS_MAP:
            values["status_text"] = BATTERY_STATUS_MAP[values["status"]]
        else:
            values["status_text"] = "Unknown"

        return values

    @property
    def is_valid(self) -> bool:
        valid = False

        if self.state_of_charge < 0:
            logger.warning("Battery state of charge is negative")
        elif self.state_of_health < 0:
            logger.warning("Battery state of health is negative")
        elif self.current < -1000000:
            logger.warning("Battery current is a huge negative")
        else:
            valid = True

        return valid

    def prepare_point(self, measurement: str = "battery_raw") -> Point:
        point = Point(measurement)
        point.field("current", self.current)
        point.field("voltage", self.voltage)
        point.field("state_of_charge", self.state_of_charge)
        point.field("state_of_health", self.state_of_health)

        if self.info.unit:
            point.tag("unit", self.info.unit.key)

        return point

    def homeassistant_device_info_with_name(self, name: str) -> dict[str, Any]:
        return self.info.homeassistant_device_info(name)
