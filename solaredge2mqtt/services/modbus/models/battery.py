
from influxdb_client import Point
from pydantic import Field

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.models.base import ModbusComponent, ModbusDeviceInfo
from solaredge2mqtt.services.modbus.sunspec.values import BATTERY_STATUS_MAP


class ModbusBattery(ModbusComponent):
    COMPONENT = "battery"

    status: int = Field(**HASensor.STATUS.field("Status"))
    status_text: str = Field(**HASensor.STATUS.field("Status text"))
    current: float = Field(**HASensor.CURRENT_A.field("current"))
    voltage: float = Field(**HASensor.VOLTAGE_V.field("voltage"))
    power: float = Field(**HASensor.POWER_W.field("power"))
    state_of_charge: float = Field(
        **HASensor.BATTERY.field("state of charge"))
    state_of_health: float = Field(
        **HASensor.BATTERY.field("state of health"))

    def __init__(self, info: ModbusDeviceInfo, data: dict[str, str | int]) -> None:
        status = data["status"]
        if status in BATTERY_STATUS_MAP:
            status_text = BATTERY_STATUS_MAP[data["status"]]
        else:
            status_text = "Unknown"

        current = round(data["instantaneous_current"], 2)
        voltage = round(data["instantaneous_voltage"], 2)
        power = round(data["instantaneous_power"], 2)
        state_of_charge = round(data["soe"], 2)
        state_of_health = round(data["soh"], 2)

        super().__init__(
            info=info,
            status=status,
            status_text=status_text,
            current=current,
            voltage=voltage,
            power=power,
            state_of_charge=state_of_charge,
            state_of_health=state_of_health,
        )

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

        if self.has_unit:
            point.tag("unit", self.info.unit.key)

        return point

    def homeassistant_device_info_with_name(self, name: str) -> dict[str, any]:
        return self.info.homeassistant_device_info(name)
