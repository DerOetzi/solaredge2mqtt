from __future__ import annotations
from typing import Any, Dict, Optional, ClassVar

from enum import Enum

from pydantic import BaseModel, model_serializer
from solaredge_modbus import (
    BATTERY_STATUS_MAP,
    C_SUNSPEC_DID_MAP,
    INVERTER_STATUS_MAP,
    sunspecDID,
)


class EnumModel(Enum):
    def __new__(cls, *args):
        obj = object.__new__(cls)
        obj._value_ = args[0]
        return obj

    def __str__(self) -> str:
        return str(self._value_)

    def __repr__(self) -> str:
        return str(self._value_)

    def __eq__(self, obj) -> bool:
        return isinstance(obj, self.__class__) and self.value == obj.value

    def __hash__(self):
        return hash(self.value)

    @classmethod
    def from_string(cls, value: str):
        for item in cls.__members__.values():
            if item.value == value:
                return item
        raise ValueError(f"No enum value {value} found.")

    @model_serializer
    def serialize(self):
        return self.value


class SunSpecInfo(BaseModel):
    manufacturer: str
    model: str
    option: Optional[str] = None
    sunspec_type: str
    version: str
    serialnumber: str

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, str]:
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

        return values


class InfluxDBModel(BaseModel):
    def influxdb_fields(self, prefix: Optional[str] = None) -> Dict[str, Any]:
        fields = {}
        for attr, value in self.__dict__.items():
            if attr == "info":
                continue
            if isinstance(value, InfluxDBModel):
                attr_name = attr
                if prefix is not None:
                    attr_name = f"{prefix}_{attr_name}"
                fields = {**fields, **value.influxdb_fields(attr_name)}
            else:
                if prefix is not None:
                    attr = f"{prefix}_{attr}"
                fields[attr] = float(value) if isinstance(value, int) else value
        return fields


class ComponentValueGroup(InfluxDBModel):
    @staticmethod
    def scale_value(
        data: Dict[str, str | int],
        value_key: str,
        scale_key: Optional[str] = None,
        digits: Optional[int] = 2,
    ) -> float:
        if scale_key is None:
            scale_key = f"{value_key}_scale"

        value = int(data[value_key])
        scale = int(data[scale_key])

        return round(value * 10**scale, digits)

    @staticmethod
    def is_three_phase(data: Dict[str, Any]) -> bool:
        return data["c_sunspec_did"] in [
            sunspecDID.THREE_PHASE_INVERTER.value,
            sunspecDID.WYE_THREE_PHASE_METER.value,
            sunspecDID.DELTA_THREE_PHASE_METER.value,
        ]


class Component(ComponentValueGroup):
    COMPONENT: ClassVar[str] = "unknown"
    SOURCE: ClassVar[str] = "unknown"

    @property
    def influxdb_tags(self) -> Dict[str, str]:
        return {
            "component": self.COMPONENT,
            "source": self.SOURCE,
        }


class SunSpecComponent(Component):
    SOURCE = "modbus"

    info: SunSpecInfo

    def __init__(self, data: Dict[str, str | int], **kwargs):
        info = SunSpecInfo.map(data)
        super().__init__(info=info, **kwargs)

    @property
    def influxdb_tags(self) -> Dict[str, str]:
        return {
            **super().influxdb_tags,
            "manufacturer": self.info.manufacturer,
            "model": self.info.model,
            "option": self.info.option,
            "sunspec_type": self.info.sunspec_type,
            "serialnumber": self.info.serialnumber,
        }


class SunSpecACCurrent(ComponentValueGroup):
    actual: float
    l1: float
    l2: Optional[float] = None
    l3: Optional[float] = None

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        values = {
            "actual": cls.scale_value(data, "current"),
            "l1": cls.scale_value(data, "l1_current", "current_scale"),
        }

        if cls.is_three_phase(data):
            values["l2"] = cls.scale_value(data, "l2_current", "current_scale")
            values["l3"] = cls.scale_value(data, "l3_current", "current_scale")

        return values


class SunSpecACVoltage(ComponentValueGroup):
    l1: Optional[float] = None
    l2: Optional[float] = None
    l3: Optional[float] = None
    l1n: Optional[float] = None
    l2n: Optional[float] = None
    l3n: Optional[float] = None

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        values = {}
        for phase in ["l1", "l2", "l3"]:
            if f"{phase}_voltage" in data:
                values[phase] = cls.scale_value(
                    data, f"{phase}_voltage", "voltage_scale"
                )

            if f"{phase}n_voltage" in data:
                values[f"{phase}n"] = cls.scale_value(
                    data, f"{phase}n_voltage", "voltage_scale"
                )

        return values


class SunSpecACPower(ComponentValueGroup):
    actual: float
    reactive: float
    apparent: float
    factor: float

    @classmethod
    def map(cls, data: Dict[str, str | int], power_key: str) -> Dict[str, Any]:
        return {
            "actual": cls.scale_value(data, power_key),
            "reactive": cls.scale_value(data, "power_reactive"),
            "apparent": cls.scale_value(data, "power_apparent"),
            "factor": cls.scale_value(data, "power_factor"),
        }


class SunSpecAC(ComponentValueGroup):
    current: SunSpecACCurrent
    voltage: SunSpecACVoltage
    power: SunSpecACPower
    frequency: float

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, Any]:
        return {
            "current": SunSpecACCurrent.map(data),
            "voltage": SunSpecACVoltage.map(data),
            "power": SunSpecACPower.map(data, "power_ac"),
            "frequency": cls.scale_value(data, "frequency"),
        }


class SunSpecEnergy(ComponentValueGroup):
    totalexport: float
    totalimport: float

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        return {
            "totalexport": cls.scale_value(
                data, "export_energy_active", "energy_active_scale"
            ),
            "totalimport": cls.scale_value(
                data, "import_energy_active", "energy_active_scale"
            ),
        }


class SunSpecDC(ComponentValueGroup):
    current: float
    voltage: float
    power: float

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, Any]:
        return {
            "current": cls.scale_value(data, "current_dc"),
            "voltage": cls.scale_value(data, "voltage_dc"),
            "power": cls.scale_value(data, "power_dc"),
        }


class SunSpecInverter(SunSpecComponent):
    COMPONENT = "inverter"

    ac: SunSpecAC
    dc: SunSpecDC
    energytotal: float
    status: str

    def __init__(self, data: Dict[str, str | int]):
        ac = SunSpecAC.map(data)
        dc = SunSpecDC.map(data)
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

    def __init__(self, data: Dict[str, str | int]):
        current = SunSpecACCurrent.map(data)
        voltage = SunSpecACVoltage.map(data)
        power = SunSpecACPower.map(data, "power")
        energy = SunSpecEnergy.map(data)
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

    def __init__(self, data: Dict[str, str | int]):
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


class WallboxAPI(Component):
    COMPONENT = "wallbox"
    SOURCE = "api"

    power: float
    state: str
    vehicle_plugged: bool
    max_current: float

    def __init__(self, data: Dict[str, str | int]):
        power = round(data["meter"]["totalActivePower"] / 1000)
        state = data["state"]
        vehicle_connected = bool(data["vehiclePlugged"])
        max_current = float(data["maxCurrent"])

        super().__init__(
            power=power,
            state=state,
            vehicle_plugged=vehicle_connected,
            max_current=max_current,
        )


class InverterPowerflow(InfluxDBModel):
    power: int
    consumption: int
    production: int
    pv_production: int
    battery_production: int

    @staticmethod
    def calc(
        inverter_data: SunSpecInverter,
        battery: BatteryPowerflow,
    ) -> InverterPowerflow:
        power = int(inverter_data.ac.power.actual)

        if power >= 0:
            consumption = 0
            production = power
            if battery.discharge > 0:
                battery_factor = battery.discharge / inverter_data.dc.power
                battery_production = int(round(production * battery_factor))
                battery_production = min(battery_production, production)
                pv_production = production - battery_production
            else:
                battery_production = 0
                pv_production = production

        else:
            consumption = int(abs(power))
            production = 0
            pv_production = 0
            battery_production = 0

        return InverterPowerflow(
            power=power,
            consumption=consumption,
            production=production,
            pv_production=pv_production,
            battery_production=battery_production,
        )


class GridPowerflow(InfluxDBModel):
    power: int
    consumption: int
    delivery: int

    @staticmethod
    def calc(meters_data: Dict[str, SunSpecMeter]) -> GridPowerflow:
        grid = 0
        for meter in meters_data.values():
            if "Import" in meter.info.option and "Export" in meter.info.option:
                grid += meter.power.actual

        if grid >= 0:
            consumption = 0
            delivery = grid
        else:
            consumption = int(abs(grid))
            delivery = 0

        return GridPowerflow(power=grid, consumption=consumption, delivery=delivery)


class BatteryPowerflow(InfluxDBModel):
    power: int
    charge: int
    discharge: int

    @staticmethod
    def calc(batteries_data: Dict[str, SunSpecBattery]) -> BatteryPowerflow:
        batteries_power = 0
        for battery in batteries_data.values():
            batteries_power += battery.power

        if batteries_power >= 0:
            charge = batteries_power
            discharge = 0
        else:
            charge = 0
            discharge = abs(batteries_power)

        return BatteryPowerflow(
            power=batteries_power, charge=charge, discharge=discharge
        )


class ConsumerPowerflow(InfluxDBModel):
    house: int
    evcharger: int = 0
    inverter: int

    total: int

    used_pv_production: int
    used_battery_production: int

    @staticmethod
    def calc(
        inverter: InverterPowerflow, grid: GridPowerflow, evcharger: int
    ) -> ConsumerPowerflow:
        house = int(abs(grid.power - inverter.power))
        if evcharger < house:
            house -= evcharger
        else:
            # Happens when EV Charger starts up and meters are not yet updated
            evcharger = 0

        total = house + evcharger + inverter.consumption

        if inverter.pv_production > inverter.production - grid.delivery:
            pv_production = inverter.pv_production - grid.delivery
        else:
            pv_production = inverter.pv_production

        if inverter.battery_production > inverter.production - grid.delivery:
            battery_production = inverter.battery_production - grid.delivery
        else:
            battery_production = inverter.battery_production

        return ConsumerPowerflow(
            house=house,
            evcharger=evcharger,
            used_pv_production=pv_production,
            used_battery_production=battery_production,
            inverter=inverter.consumption,
            total=total,
        )

    def is_valid(self) -> bool:
        return self.total >= self.used_battery_production + self.used_pv_production


class PowerFlow(InfluxDBModel):
    pv_production: int
    inverter: InverterPowerflow
    grid: GridPowerflow
    battery: BatteryPowerflow
    consumer: ConsumerPowerflow

    @staticmethod
    def calc(
        inverter_data: SunSpecInverter,
        meters_data: Dict[str, SunSpecMeter],
        batteries_data: Dict[str, SunSpecBattery],
        evcharger: Optional[int] = 0,
    ) -> PowerFlow:
        grid = GridPowerflow.calc(meters_data)
        battery = BatteryPowerflow.calc(batteries_data)

        if inverter_data.ac.power.actual > 0:
            pv_production = int(inverter_data.dc.power + battery.power)
            if pv_production < 0:
                pv_production = 0
        else:
            pv_production = 0

        inverter = InverterPowerflow.calc(inverter_data, battery)

        consumer = ConsumerPowerflow.calc(inverter, grid, evcharger)

        return PowerFlow(
            pv_production=pv_production,
            inverter=inverter,
            grid=grid,
            battery=battery,
            consumer=consumer,
        )


class LogicalInfo(BaseModel):
    id: str
    serialnumber: Optional[str]
    name: str
    type: str

    @staticmethod
    def map(data: Dict[str, str | int]) -> Dict[str, str]:
        return {
            "id": str(data["id"]),
            "serialnumber": data["serialNumber"],
            "name": data["name"],
            "type": data["type"],
        }


class LogicalInverter(BaseModel):
    info: LogicalInfo
    energy: Optional[float]
    strings: list[LogicalString] = []


class LogicalString(BaseModel):
    info: LogicalInfo
    energy: Optional[float]
    modules: list[LogicalModule] = []


class LogicalModule(BaseModel):
    info: LogicalInfo
    energy: Optional[float]
