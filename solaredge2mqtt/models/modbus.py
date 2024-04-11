from __future__ import annotations

from influxdb_client import Point
from pydantic import Field
from solaredge_modbus import BATTERY_STATUS_MAP, C_SUNSPEC_DID_MAP, INVERTER_STATUS_MAP

from solaredge2mqtt.logging import logger
from solaredge2mqtt.models.base import (
    Component,
    ComponentValueGroup,
    Solaredge2MQTTBaseModel,
)


class SunSpecInfo(Solaredge2MQTTBaseModel):
    manufacturer: str
    model: str
    option: str | None = None
    sunspec_type: str
    version: str
    serialnumber: str

    def __init__(self, data: dict[str, str | int]) -> dict[str, str]:
        values = {
            "manufacturer": data["c_manufacturer"],
            "model": data["c_model"],
            "version": data["c_version"],
            "serialnumber": data["c_serialnumber"],
        }

        if str(data["c_sunspec_did"]) in C_SUNSPEC_DID_MAP:
            values["sunspec_type"] = C_SUNSPEC_DID_MAP[str(data["c_sunspec_did"])]
        else:
            values["sunspec_type"] = "Unknown"

        if "c_option" in data:
            values["option"] = data["c_option"]

        super().__init__(**values)

    def homeassistant_device_info(self) -> dict[str, any]:
        return {
            "name": self.model,
            "manufacturer": self.manufacturer,
            "model": self.model,
            "hw_version": self.version,
            "serial_number": self.serialnumber,
        }


class SunSpecComponent(Component):
    SOURCE = "modbus"

    info: SunSpecInfo

    def __init__(self, data: dict[str, str | int], **kwargs):
        info = SunSpecInfo(data)
        super().__init__(info=info, **kwargs)

    def model_dump_influxdb(self, exclude: list[str] | None = None) -> dict[str, any]:
        return super().model_dump_influxdb(["info", *exclude] if exclude else ["info"])

    @property
    def influxdb_tags(self) -> dict[str, str]:
        return {
            **super().influxdb_tags,
            "manufacturer": self.info.manufacturer,
            "model": self.info.model,
            "option": self.info.option,
            "sunspec_type": self.info.sunspec_type,
            "serialnumber": self.info.serialnumber,
        }

    @classmethod
    # pylint: disable=arguments-differ
    def model_json_schema(cls) -> dict[str, any]:
        schema = super().model_json_schema()
        schema["properties"].pop("info", None)
        return schema

    def homeassistant_device_info(self) -> dict[str, any]:
        return self.info.homeassistant_device_info()


class SunSpecACCurrent(ComponentValueGroup):
    actual: float = Field(title="actual", unit="A")
    l1: float = Field(title="L1", unit="A")
    l2: float | None = Field(None, title="L2", unit="A")
    l3: float | None = Field(None, title="L3", unit="A")

    def __init__(self, data: dict[str, str | int]):
        values = {"actual": self.scale_value(data, "current")}

        for phase in ["l1", "l2", "l3"]:
            if f"{phase}_current" in data:
                values[phase] = self.scale_value(
                    data, f"{phase}_current", "current_scale"
                )

        super().__init__(**values)


class SunSpecACVoltage(ComponentValueGroup):
    l1: float | None = Field(None, title="L1", unit="V")
    l2: float | None = Field(None, title="L2", unit="V")
    l3: float | None = Field(None, title="L3", unit="V")
    l1n: float | None = Field(None, title="L1N", unit="V")
    l2n: float | None = Field(None, title="L2N", unit="V")
    l3n: float | None = Field(None, title="L3N", unit="V")

    def __init__(self, data: dict[str, str | int]):
        values = {}
        for phase in ["l1", "l2", "l3"]:
            if f"{phase}_voltage" in data:
                values[phase] = self.scale_value(
                    data, f"{phase}_voltage", "voltage_scale"
                )

            if f"{phase}n_voltage" in data:
                values[f"{phase}n"] = self.scale_value(
                    data, f"{phase}n_voltage", "voltage_scale"
                )

        super().__init__(**values)


class SunSpecACPower(ComponentValueGroup):
    actual: float = Field(title="actual", unit="W")
    reactive: float = Field(title="reactive", unit="W")
    apparent: float = Field(title="apparent", unit="W")
    factor: float = Field(title="power factor")

    def __init__(self, data: dict[str, str | int], power_key: str):
        actual = self.scale_value(data, power_key)
        reactive = self.scale_value(data, "power_reactive")
        apparent = self.scale_value(data, "power_apparent")
        factor = self.scale_value(data, "power_factor")
        super().__init__(
            actual=actual, reactive=reactive, apparent=apparent, factor=factor
        )


class SunSpecAC(ComponentValueGroup):
    current: SunSpecACCurrent = Field(title="Current")
    voltage: SunSpecACVoltage = Field(title="Voltage")
    power: SunSpecACPower = Field(title="Power")
    frequency: float = Field(title="Grid frequency")

    def __init__(self, data: dict[str, str | int]):
        current = SunSpecACCurrent(data)
        voltage = SunSpecACVoltage(data)
        power = SunSpecACPower(data, "power_ac")
        frequency = self.scale_value(data, "frequency")

        super().__init__(
            current=current, voltage=voltage, power=power, frequency=frequency
        )


class SunSpecEnergy(ComponentValueGroup):
    totalexport: float
    totalimport: float

    def __init__(self, data: dict[str, str | int]):
        super().__init__(
            totalexport=self.scale_value(
                data, "export_energy_active", "energy_active_scale"
            ),
            totalimport=self.scale_value(
                data, "import_energy_active", "energy_active_scale"
            ),
        )


class SunSpecDC(ComponentValueGroup):
    current: float = Field(title="Current", unit="A")
    voltage: float = Field(title="Voltage", unit="V")
    power: float = Field(title="Power", unit="W")

    def __init__(self, data: dict[str, str | int]):
        super().__init__(
            current=self.scale_value(data, "current_dc"),
            voltage=self.scale_value(data, "voltage_dc"),
            power=self.scale_value(data, "power_dc"),
        )


class SunSpecInverter(SunSpecComponent):
    COMPONENT = "inverter"

    ac: SunSpecAC = Field(title="AC")
    dc: SunSpecDC = Field(title="DC")
    energytotal: float = Field(
        title="Energy total", unit="Wh", ha_state_class="total_increasing"
    )
    status: str = Field(title="Inverter status", ha_type="text")

    def __init__(self, data: dict[str, str | int]):
        ac = SunSpecAC(data)
        dc = SunSpecDC(data)
        energytotal = self.scale_value(data, "energy_total")
        status = INVERTER_STATUS_MAP[data["status"]]

        super().__init__(data, ac=ac, dc=dc, energytotal=energytotal, status=status)


class SunSpecMeter(SunSpecComponent):
    COMPONENT = "meter"

    current: SunSpecACCurrent
    voltage: SunSpecACVoltage
    power: SunSpecACPower
    energy: SunSpecEnergy
    frequency: float

    def __init__(self, data: dict[str, str | int]):
        current = SunSpecACCurrent(data)
        voltage = SunSpecACVoltage(data)
        power = SunSpecACPower(data, "power")
        energy = SunSpecEnergy(data)
        frequency = self.scale_value(data, "frequency")

        super().__init__(
            data,
            current=current,
            voltage=voltage,
            power=power,
            energy=energy,
            frequency=frequency,
        )


class SunSpecBattery(SunSpecComponent):
    COMPONENT = "battery"

    status: str
    current: float
    voltage: float
    power: float
    state_of_charge: float
    state_of_health: float

    def __init__(self, data: dict[str, str | int]):
        status = BATTERY_STATUS_MAP[data["status"]]
        current = round(data["instantaneous_current"], 2)
        voltage = round(data["instantaneous_voltage"], 2)
        power = round(data["instantaneous_power"], 2)
        state_of_charge = round(data["soe"], 2)
        state_of_health = round(data["soh"], 2)

        super().__init__(
            data,
            status=status,
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

        return point
