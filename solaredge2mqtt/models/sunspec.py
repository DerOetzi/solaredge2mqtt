from typing import Any, Dict

from pydantic import BaseModel

from solaredge_modbus import C_SUNSPEC_DID_MAP, sunspecDID, INVERTER_STATUS_MAP


class SunSpecInfo(BaseModel):
    manufacturer: str
    model: str
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

        return values


class SunSpecBaseValue(BaseModel):
    @staticmethod
    def scale_value(value: int, scale: int, digits: int = 2) -> float:
        return round(value * 10**scale, digits)

    @staticmethod
    def is_three_phase(data: Dict[str, Any]) -> bool:
        return data["c_sunspec_did"] is sunspecDID.THREE_PHASE_INVERTER.value


class SunSpecACCurrent(SunSpecBaseValue):
    current: float
    l1_current: float
    l2_current: float | None
    l3_current: float | None

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        values = {
            "current": cls.scale_value(data["current"], data["current_scale"]),
            "l1_current": cls.scale_value(data["l1_current"], data["current_scale"]),
        }

        if cls.is_three_phase(data):
            values["l2_current"] = cls.scale_value(
                data["l2_current"], data["current_scale"]
            )
            values["l3_current"] = cls.scale_value(
                data["l3_current"], data["current_scale"]
            )

        return values


class SunSpecACVoltage(SunSpecBaseValue):
    l1_voltage: float
    l2_voltage: float | None
    l3_voltage: float | None
    l1n_voltage: float
    l2n_voltage: float | None
    l3n_voltage: float | None

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, float]:
        values = {
            "l1_voltage": cls.scale_value(data["l1_voltage"], data["voltage_scale"]),
            "l1n_voltage": cls.scale_value(data["l1n_voltage"], data["voltage_scale"]),
        }

        if cls.is_three_phase(data):
            values["l2_voltage"] = cls.scale_value(
                data["l2_voltage"], data["voltage_scale"]
            )
            values["l2n_voltage"] = cls.scale_value(
                data["l2n_voltage"], data["voltage_scale"]
            )
            values["l3_voltage"] = cls.scale_value(
                data["l3_voltage"], data["voltage_scale"]
            )
            values["l3n_voltage"] = cls.scale_value(
                data["l3n_voltage"], data["voltage_scale"]
            )

        return values


class SunSpecACPower(SunSpecBaseValue):
    power: float
    power_reactive: float
    power_apparent: float
    power_factor: float

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, Any]:
        return {
            "power": cls.scale_value(data["power_ac"], data["power_ac_scale"]),
            "power_reactive": cls.scale_value(
                data["power_reactive"], data["power_reactive_scale"]
            ),
            "power_apparent": cls.scale_value(
                data["power_apparent"], data["power_apparent_scale"]
            ),
            "power_factor": cls.scale_value(
                data["power_factor"], data["power_factor_scale"]
            ),
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
            "power": SunSpecACPower.map(data),
            "frequency": cls.scale_value(data["frequency"], data["frequency_scale"]),
        }


class SunSpecDC(SunSpecBaseValue):
    current: float
    voltage: float
    power: float

    @classmethod
    def map(cls, data: Dict[str, str | int]) -> Dict[str, Any]:
        return {
            "current": cls.scale_value(data["current_dc"], data["current_dc_scale"]),
            "voltage": cls.scale_value(data["voltage_dc"], data["voltage_dc_scale"]),
            "power": cls.scale_value(data["power_dc"], data["power_dc_scale"]),
        }


class SunSpecInverter(BaseModel):
    info: SunSpecInfo
    ac: SunSpecAC
    dc: SunSpecDC
    status: str

    def __init__(self, data: Dict[str, str | int]):
        info = SunSpecInfo.map(data)
        ac = SunSpecAC.map(data)
        dc = SunSpecDC.map(data)
        status = INVERTER_STATUS_MAP[data["status"]]

        super().__init__(info=info, ac=ac, dc=dc, status=status)


class SunSpecMeter(BaseModel):
    info: SunSpecInfo

    def __init__(self, data: Dict[str, str | int]):
        info = SunSpecInfo.map(data)

        super().__init__(info=info)


class SunSpecBattery(BaseModel):
    info: SunSpecInfo

    def __init__(self, data: Dict[str, str | int]):
        info = SunSpecInfo.map(data)

        super().__init__(info=info)
