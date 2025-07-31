from typing import Type

from pymodbus.client import ModbusTcpClient

from solaredge2mqtt.core.models import EnumModel

SunSpecRawData = str | int | float

SunSpecInputData = int | float | str | bool

SunSpecPayload = dict[str, SunSpecRawData]


C_SUNSPEC_DID_MAP = {
    101: "Single Phase Inverter",
    102: "Split Phase Inverter",
    103: "Three Phase Inverter",
    201: "Single Phase Meter",
    202: "Split Phase Meter",
    203: "Wye 3P1N Three Phase Meter",
    204: "Delta 3P Three Phase Meter",
    802: "Battery",
    803: "Lithium Ion Bank Battery",
    804: "Lithium Ion String Battery",
    805: "Lithium Ion Module Battery",
    806: "Flow Battery",
    807: "Flow String Battery",
    808: "Flow Module Battery",
    809: "Flow Stack Battery",
}

INVERTER_STATUS_MAP = {
    1: "Off",
    2: "Sleeping (auto-shutdown) – Night mode",
    3: "Grid Monitoring/wake-up",
    4: "Inverter is ON and producing power",
    5: "Production (curtailed)",
    6: "Shutting down",
    7: "Fault",
    8: "Maintenance/setup",
}

BATTERY_STATUS_MAP = {
    0: "Off",
    1: "Standby",
    2: "Initializing",
    3: "Charge",
    4: "Discharge",
    5: "Fault",
    6: "Preserve Charge",
    7: "Idle",
    10: "Power Saving",
}

EXPORT_CONTROL_MODE_MAP = {
    0: "Disabled",
    1: "Direct Export Limitation",
    2: "Indirect Export Limitation",
    3: "Production Limitation"
}

REACTIVE_POWER_CONFIG_MAP = {
    0: "Fixed CosPhi",
    1: "Fixed Q",
    2: "CosPhi(P)",
    3: "Q(U) + Q(P)",
    4: "RRCR Mode"
}


class SunSpecValueType(EnumModel):
    INT16 = "int16", int, 0x8000, "h"
    UINT16 = "uint16", int, 0xFFFF, "H"
    INT32 = "int32", int, 0x80000000, "i"
    UINT32 = "uint32", int, 0xFFFFFFFF, "I"
    UINT64 = "uint64", int, 0xFFFFFFFFFFFFFFFF, "q"
    FLOAT32 = "float32", float, 0x7FC00000, "f"
    STRING = "string", str, "", "s"

    def __init__(
        self,
        identifier: str,
        typed: Type[SunSpecRawData],
        not_implemented_value: SunSpecRawData,
        data_type: str,
    ):
        # pylint: disable=super-init-not-called
        self._identifier = identifier
        self._typed = typed
        self._not_implemented_value = not_implemented_value
        self._data_type = self.__modbus_data_type(data_type)

    @staticmethod
    def __modbus_data_type(data_type: str) -> ModbusTcpClient.DATATYPE:
        for datatype in ModbusTcpClient.DATATYPE:
            if datatype.value[0] == data_type:
                return datatype

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def typed(self) -> Type[SunSpecRawData]:
        return self._typed

    @property
    def length(self) -> int:
        return self._data_type.value[1]

    @property
    def not_implemented_value(self) -> SunSpecRawData:
        return self._not_implemented_value

    @property
    def data_type(self) -> ModbusTcpClient.DATATYPE:
        return self._data_type
