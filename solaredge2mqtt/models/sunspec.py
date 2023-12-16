from typing import Any, Dict, Optional

from pydantic import BaseModel
from solaredge_modbus import (
    BATTERY_STATUS_MAP,
    C_SUNSPEC_DID_MAP,
    INVERTER_STATUS_MAP,
    sunspecDID,
)


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


class SunSpecBaseValue(BaseModel):
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


class SunSpecACCurrent(SunSpecBaseValue):
    current: float
    l1_current: float
    l2_current: Optional[float] = None
    l3_current: Optional[float] = None

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        values = {
            "current": cls.scale_value(data, "current"),
            "l1_current": cls.scale_value(data, "l1_current", "current_scale"),
        }

        if cls.is_three_phase(data):
            values["l2_current"] = cls.scale_value(data, "l2_current", "current_scale")
            values["l3_current"] = cls.scale_value(data, "l1_current", "current_scale")

        return values


class SunSpecACVoltage(SunSpecBaseValue):
    l1_voltage: Optional[float] = None
    l2_voltage: Optional[float] = None
    l3_voltage: Optional[float] = None
    l1n_voltage: Optional[float] = None
    l2n_voltage: Optional[float] = None
    l3n_voltage: Optional[float] = None

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        values = {}
        for phase in ["l1", "l2", "l3"]:
            if f"{phase}_voltage" in data:
                values[f"{phase}_voltage"] = cls.scale_value(
                    data, f"{phase}_voltage", "voltage_scale"
                )

            if f"{phase}n_voltage" in data:
                values[f"{phase}n_voltage"] = cls.scale_value(
                    data, f"{phase}n_voltage", "voltage_scale"
                )

        return values


class SunSpecACPower(SunSpecBaseValue):
    power: float
    power_reactive: float
    power_apparent: float
    power_factor: float

    @classmethod
    def map(cls, data: Dict[str, str | int], power_key: str) -> Dict[str, Any]:
        return {
            "power": cls.scale_value(data, power_key),
            "power_reactive": cls.scale_value(data, "power_reactive"),
            "power_apparent": cls.scale_value(data, "power_apparent"),
            "power_factor": cls.scale_value(data, "power_factor"),
        }


class SunSpecAC(SunSpecBaseValue):
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


class SunSpecEnergy(SunSpecBaseValue):
    total_export: float
    total_import: float

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        return {
            "total_export": cls.scale_value(
                data, "export_energy_active", "energy_active_scale"
            ),
            "total_import": cls.scale_value(
                data, "import_energy_active", "energy_active_scale"
            ),
        }


class SunSpecDC(SunSpecBaseValue):
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


class SunSpecInverter(SunSpecBaseValue):
    info: SunSpecInfo
    ac: SunSpecAC
    dc: SunSpecDC
    energy_total: float
    status: str

    def __init__(self, data: Dict[str, str | int]):
        info = SunSpecInfo.map(data)
        ac = SunSpecAC.map(data)
        dc = SunSpecDC.map(data)
        energy_total = self.scale_value(data, "energy_total")
        status = INVERTER_STATUS_MAP[data["status"]]

        super().__init__(
            info=info, ac=ac, dc=dc, energy_total=energy_total, status=status
        )


class SunSpecMeter(SunSpecBaseValue):
    info: SunSpecInfo
    current: SunSpecACCurrent
    voltage: SunSpecACVoltage
    power: SunSpecACPower
    energy: SunSpecEnergy
    frequency: float

    def __init__(self, data: Dict[str, str | int]):
        info = SunSpecInfo.map(data)
        current = SunSpecACCurrent.map(data)
        voltage = SunSpecACVoltage.map(data)
        power = SunSpecACPower.map(data, "power")
        energy = SunSpecEnergy.map(data)
        frequency = self.scale_value(data, "frequency")

        super().__init__(
            info=info,
            current=current,
            voltage=voltage,
            power=power,
            energy=energy,
            frequency=frequency,
        )


class SunSpecBattery(BaseModel):
    info: SunSpecInfo
    status: str
    current: float
    voltage: float
    power: float
    state_of_charge: float
    state_of_health: float

    def __init__(self, data: Dict[str, str | int]):
        info = SunSpecInfo.map(data)
        status = BATTERY_STATUS_MAP[data["status"]]
        current = round(data["instantaneous_current"], 2)
        voltage = round(data["instantaneous_voltage"], 2)
        power = round(data["instantaneous_power"], 2)
        state_of_charge = round(data["soe"], 2)
        state_of_health = round(data["soh"], 2)

        super().__init__(
            info=info,
            status=status,
            current=current,
            voltage=voltage,
            power=power,
            state_of_charge=state_of_charge,
            state_of_health=state_of_health,
        )
