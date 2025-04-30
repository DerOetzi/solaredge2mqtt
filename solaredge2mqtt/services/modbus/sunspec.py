from __future__ import annotations

from typing import Type

from pymodbus.client import ModbusTcpClient

from solaredge2mqtt.core.models import EnumModel

SunSpecRawData = str | int

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


class SunSpecRequestRegisterBundle:
    @classmethod
    def from_registers(
        cls, registers: list[SunSpecRegister], required_only: bool = True
    ) -> list[SunSpecRequestRegisterBundle]:

        sorted_registers = sorted(registers, key=lambda reg: reg.address)

        bundles = cls._bundle_registers(required_only, sorted_registers)

        if required_only:
            bundles = cls._add_not_required(sorted_registers, bundles)

        return bundles

    @classmethod
    def _bundle_registers(
        cls, required_only, sorted_registers
    ) -> list[SunSpecRequestRegisterBundle]:
        bundles = []
        current_bundle = cls()

        for register in [
            reg for reg in sorted_registers if not required_only or reg.required
        ]:
            if (
                current_bundle.length > 0
                and register.end_address - current_bundle.address + 1 > 120
            ):
                bundles.append(current_bundle)
                current_bundle = cls()

            current_bundle.add_register(register)

        if current_bundle.length > 0:
            bundles.append(current_bundle)

        return bundles

    @staticmethod
    def _add_not_required(
        sorted_registers, bundles
    ) -> list[SunSpecRequestRegisterBundle]:
        for bundle in bundles:
            not_required_registers = [
                reg
                for reg in sorted_registers
                if not reg.required
                and reg.address >= bundle.address
                and reg.end_address <= bundle.end_address
            ]

            for reg in not_required_registers:
                bundle.add_register(reg)

        return bundles

    def __init__(self):
        self._registers: list[SunSpecRegister] = []

    def add_register(self, register: SunSpecRegister) -> None:
        self._registers.append(register)

    @property
    def registers(self) -> set[SunSpecRegister]:
        return self._registers

    @property
    def address(self) -> int:
        return min([register.address for register in self._registers])

    @property
    def end_address(self) -> int:
        return max([register.end_address for register in self._registers])

    @property
    def length(self) -> int:
        length = self.end_address - self.address if self._registers else 0

        return length

    def decode_response(
        self, registers: list[int], data: dict[str, SunSpecPayload]
    ) -> dict[str, SunSpecPayload]:
        for register in self._registers:
            offset = register.address - self.address
            response_slice = registers[offset : offset + register.length]
            data = register.decode_response(response_slice, data)

        return data


class SunSpecRegister(EnumModel):
    def __init__(
        self,
        identifier: str,
        address: int,
        value_type: SunSpecValueType,
        required: bool = False,
        length: int = 0,
    ) -> None:
        # pylint: disable=super-init-not-called
        self._identifier = identifier
        self._address = address
        self._value_type = value_type

        if length != 0:
            self._length = length
        elif value_type.length != 0:
            self._length = value_type.length

        self._required = required

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def address(self) -> int:
        return self._address

    @property
    def end_address(self) -> int:
        return self.address + self.length

    @property
    def value_type(self) -> SunSpecValueType:
        return self._value_type

    @property
    def length(self) -> int:
        return self._length

    @property
    def required(self) -> bool:
        return self._required

    @staticmethod
    def wordorder() -> str:
        return "big"

    @classmethod
    def request_bundles(
        cls, required_only: bool = True
    ) -> list[SunSpecRequestRegisterBundle]:
        if not hasattr(cls, "_cached_bundles"):
            cls._cached_bundles = SunSpecRequestRegisterBundle.from_registers(
                cls, required_only
            )
        return cls._cached_bundles

    def decode_response(
        self, registers: list[int], data: dict[str, SunSpecPayload]
    ) -> dict[str, SunSpecPayload]:
        value = ModbusTcpClient.convert_from_registers(
            registers, self.value_type.data_type, word_order=self.wordorder()
        )

        if self.value_type == SunSpecValueType.STRING:
            value = value.strip("\x00").rstrip()
        elif value == self.value_type.not_implemented_value:
            value = False

        data[self.identifier] = value

        return data


class SunSpecOffset(EnumModel):
    def __init__(self, identifier: str, offset: int):
        # pylint: disable=super-init-not-called
        self._identifier = identifier
        self._offset = offset

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def offset(self) -> int:
        return self._offset


class SunSpecMeterInfoRegister(SunSpecRegister):
    C_MANUFACTURER = "c_manufacturer", 40123, SunSpecValueType.STRING, True, 16
    C_MODEL = "c_model", 40139, SunSpecValueType.STRING, True, 16
    C_OPTION = "c_option", 40155, SunSpecValueType.STRING, True, 8
    C_VERSION = "c_version", 40163, SunSpecValueType.STRING, True, 8
    C_SERIALNUMBER = "c_serialnumber", 40171, SunSpecValueType.STRING, True, 16
    C_DEVICEADDRESS = "c_deviceaddress", 40187, SunSpecValueType.UINT16, True
    C_SUNSPEC_DID = "c_sunspec_did", 40188, SunSpecValueType.UINT16, True
    C_SUNSPEC_LENGTH = (
        "c_sunspec_length",
        40189,
        SunSpecValueType.UINT16,
    )


class SunSpecMeterRegister(SunSpecRegister):
    CURRENT = "current", 40190, SunSpecValueType.INT16, True
    L1_CURRENT = "l1_current", 40191, SunSpecValueType.INT16
    L2_CURRENT = "l2_current", 40192, SunSpecValueType.INT16
    L3_CURRENT = "l3_current", 40193, SunSpecValueType.INT16
    CURRENT_SCALE = "current_scale", 40194, SunSpecValueType.INT16, True

    VOLTAGE_LN = "voltage_ln", 40195, SunSpecValueType.INT16, True
    L1N_VOLTAGE = "l1n_voltage", 40196, SunSpecValueType.INT16
    L2N_VOLTAGE = "l2n_voltage", 40197, SunSpecValueType.INT16
    L3N_VOLTAGE = "l3n_voltage", 40198, SunSpecValueType.INT16
    VOLTAGE_LL = "voltage_lln", 40199, SunSpecValueType.INT16, True
    L12_VOLTAGE = "l12_voltage", 40200, SunSpecValueType.INT16
    L23_VOLTAGE = "l23_voltage", 40201, SunSpecValueType.INT16
    L31_VOLTAGE = "l31_voltage", 40202, SunSpecValueType.INT16
    VOLTAGE_SCALE = "voltage_scale", 40203, SunSpecValueType.INT16, True

    FREQUENCY = "frequency", 40204, SunSpecValueType.UINT16, True
    FREQUENCY_SCALE = "frequency_scale", 40205, SunSpecValueType.INT16, True

    POWER = "power", 40206, SunSpecValueType.INT16, True
    L1_POWER = "l1_power", 40207, SunSpecValueType.INT16
    L2_POWER = "l2_power", 40208, SunSpecValueType.INT16
    L3_POWER = "l3_power", 40209, SunSpecValueType.INT16
    POWER_SCALE = "power_scale", 40210, SunSpecValueType.INT16, True

    POWER_APPARENT = "power_apparent", 40211, SunSpecValueType.INT16, True
    L1_POWER_APPARENT = "l1_power_apparent", 40212, SunSpecValueType.INT16
    L2_POWER_APPARENT = "l2_power_apparent", 40213, SunSpecValueType.INT16
    L3_POWER_APPARENT = "l3_power_apparent", 40214, SunSpecValueType.INT16
    POWER_APPARENT_SCALE = "power_apparent_scale", 40215, SunSpecValueType.INT16, True

    POWER_REACTIVE = "power_reactive", 40216, SunSpecValueType.INT16, True
    L1_POWER_REACTIVE = "l1_power_reactive", 40217, SunSpecValueType.INT16
    L2_POWER_REACTIVE = "l2_power_reactive", 40218, SunSpecValueType.INT16
    L3_POWER_REACTIVE = "l3_power_reactive", 40219, SunSpecValueType.INT16
    POWER_REACTIVE_SCALE = "power_reactive_scale", 40220, SunSpecValueType.INT16, True

    POWER_FACTOR = "power_factor", 40221, SunSpecValueType.INT16, True
    L1_POWER_FACTOR = "l1_power_factor", 40222, SunSpecValueType.INT16
    L2_POWER_FACTOR = "l2_power_factor", 40223, SunSpecValueType.INT16
    L3_POWER_FACTOR = "l3_power_factor", 40224, SunSpecValueType.INT16
    POWER_FACTOR_SCALE = "power_factor_scale", 40225, SunSpecValueType.INT16, True

    EXPORT_ENERGY_ACTIVE = "export_energy_active", 40226, SunSpecValueType.UINT32, True
    L1_EXPORT_ENERGY_ACTIVE = (
        "l1_export_energy_active",
        40228,
        SunSpecValueType.UINT32,
    )
    L2_EXPORT_ENERGY_ACTIVE = (
        "l2_export_energy_active",
        40230,
        SunSpecValueType.UINT32,
    )
    L3_EXPORT_ENERY_ACTIVE = (
        "l3_export_energy_active",
        40232,
        SunSpecValueType.UINT32,
    )
    IMPORT_ENERGY_ACTIVE = "import_energy_active", 40234, SunSpecValueType.UINT32, True
    L1_IMPORT_ENERGY_ACTIVE = (
        "l1_import_energy_active",
        40236,
        SunSpecValueType.UINT32,
    )
    L2_IMPORT_ENERGY_ACTIVE = (
        "l2_import_energy_active",
        40238,
        SunSpecValueType.UINT32,
    )
    L3_IMPORT_ENERGY_ACTIVE = (
        "l3_import_energy_active",
        40240,
        SunSpecValueType.UINT32,
    )
    ENERGY_ACTIVE_SCALE = "energy_active_scale", 40242, SunSpecValueType.INT16, True

    EXPORT_ENERGY_APPARENT = "export_energy_apparent", 40243, SunSpecValueType.UINT32
    L1_EXPORT_ENERGY_APPARENT = (
        "l1_export_energy_apparent",
        40245,
        SunSpecValueType.UINT32,
    )
    L2_EXPORT_ENERGY_APPARENT = (
        "l2_export_energy_apparent",
        40247,
        SunSpecValueType.UINT32,
    )
    L3_EXPORT_ENERGY_APPARENT = (
        "l3_export_energy_apparent",
        40249,
        SunSpecValueType.UINT32,
    )
    IMPORT_ENERGY_APPARENT = "import_energy_apparent", 40251, SunSpecValueType.UINT32
    L1_IMPORT_ENERGY_APPARENT = (
        "l1_import_energy_apparent",
        40253,
        SunSpecValueType.UINT32,
    )
    L2_IMPORT_ENERGY_APPARENT = (
        "l2_import_energy_apparent",
        40255,
        SunSpecValueType.UINT32,
    )
    L3_IMPORT_ENERGY_APPARENT = (
        "l3_import_energy_apparent",
        40257,
        SunSpecValueType.UINT32,
    )
    ENERGY_APPARENT_SCALE = "energy_apparent_scale", 40259, SunSpecValueType.INT16

    IMPORT_ENERGY_REACTIVE_Q1 = (
        "import_energy_reactive_q1",
        40260,
        SunSpecValueType.UINT32,
    )
    L1_IMPORT_ENERGY_REACTIVE_Q1 = (
        "l1_import_energy_reactive_q1",
        40262,
        SunSpecValueType.UINT32,
    )
    L2_IMPORT_ENERGY_REACTIVE_Q1 = (
        "l2_import_energy_reactive_q1",
        40264,
        SunSpecValueType.UINT32,
    )
    L3_IMPORT_ENERGY_REACTIVE_Q1 = (
        "l3_import_energy_reactive_q1",
        40266,
        SunSpecValueType.UINT32,
    )
    IMPORT_ENERGY_REACTIVE_Q2 = (
        "import_energy_reactive_q2",
        40268,
        SunSpecValueType.UINT32,
    )
    L1_IMPORT_ENERGY_REACTIVE_Q2 = (
        "l1_import_energy_reactive_q2",
        40270,
        SunSpecValueType.UINT32,
    )
    L2_IMPORT_ENERGY_REACTIVE_Q2 = (
        "l2_import_energy_reactive_q2",
        40272,
        SunSpecValueType.UINT32,
    )
    L3_IMPORT_ENERGY_REACTIVE_Q2 = (
        "l3_import_energy_reactive_q2",
        40274,
        SunSpecValueType.UINT32,
    )
    EXPORT_ENERGY_REACTIVE_Q3 = (
        "export_energy_reactive_q3",
        40276,
        SunSpecValueType.UINT32,
    )
    L1_EXPORT_ENERGY_REACTIVE_Q3 = (
        "l1_export_energy_reactive_q3",
        40278,
        SunSpecValueType.UINT32,
    )
    L2_EXPORT_ENERGY_REACTIVE_Q3 = (
        "l2_export_energy_reactive_q3",
        40280,
        SunSpecValueType.UINT32,
    )
    L3_EXPORT_ENERGY_REACTIVE_Q3 = (
        "l3_export_energy_reactive_q3",
        40282,
        SunSpecValueType.UINT32,
    )
    EXPORT_ENERGY_REACTIVE_Q4 = (
        "export_energy_reactive_q4",
        40284,
        SunSpecValueType.UINT32,
    )
    L1_EXPORT_ENERGY_REACTIVE_Q4 = (
        "l1_export_energy_reactive_q4",
        40286,
        SunSpecValueType.UINT32,
    )
    L2_EXPORT_ENERGY_REACTIVE_Q4 = (
        "l2_export_energy_reactive_q4",
        40288,
        SunSpecValueType.UINT32,
    )
    L3_EXPORT_ENERGY_REACTIVE_Q4 = (
        "l3_export_energy_reactive_q4",
        40290,
        SunSpecValueType.UINT32,
    )
    ENERGY_REACTIVE_SCALE = "energy_reactive_scale", 40292, SunSpecValueType.INT16


class SunSpecMeterOffset(SunSpecOffset):
    METER0 = "meter0", 0
    METER1 = "meter1", 174
    METER2 = "meter2", 348


class SunSpecBatteryInfoRegister(SunSpecRegister):
    C_MANUFACTURER = "c_manufacturer", 57600, SunSpecValueType.STRING, True, 16
    C_MODEL = "c_model", 57616, SunSpecValueType.STRING, True, 16
    C_VERSION = "c_version", 57632, SunSpecValueType.STRING, True, 16
    C_SERIALNUMBER = "c_serialnumber", 57648, SunSpecValueType.STRING, True, 16
    C_DEVICEADDRESS = "c_deviceaddress", 57664, SunSpecValueType.UINT16, True
    C_SUNSPEC_DID = "c_sunspec_did", 57665, SunSpecValueType.UINT16, True


class SunSpecBatteryRegister(SunSpecRegister):
    RATED_ENERGY = "rated_energy", 57666, SunSpecValueType.FLOAT32
    MAXIMUM_CHARGE_CONTINUOUS_POWER = (
        "maximum_charge_continuous_power",
        57668,
        SunSpecValueType.FLOAT32,
    )
    MAXIMUM_DISCHARGE_CONTINUOUS_POWER = (
        "maximum_discharge_continuous_power",
        57670,
        SunSpecValueType.FLOAT32,
    )
    MAXIMUM_CHARGE_PEAK_POWER = (
        "maximum_charge_peak_power",
        57672,
        SunSpecValueType.FLOAT32,
    )
    MAXIMUM_DISCHARGE_PEAK_POWER = (
        "maximum_discharge_peak_power",
        57674,
        SunSpecValueType.FLOAT32,
    )

    AVERAGE_TEMPERATURE = "average_temperature", 57708, SunSpecValueType.FLOAT32
    MAXIMUM_TEMPERATURE = "maximum_temperature", 57710, SunSpecValueType.FLOAT32

    INSTANTANEOUS_VOLTAGE = (
        "instantaneous_voltage",
        57712,
        SunSpecValueType.FLOAT32,
        True,
    )
    INSTANTANEOUS_CURRENT = (
        "instantaneous_current",
        57714,
        SunSpecValueType.FLOAT32,
        True,
    )
    INSTANTANEOUS_POWER = "instantaneous_power", 57716, SunSpecValueType.FLOAT32, True

    LIFETIME_EXPORT_ENERGY_COUNTER = (
        "lifetime_export_energy_counter",
        57718,
        SunSpecValueType.UINT64,
    )
    LIFETIME_IMPORT_ENERGY_COUNTER = (
        "lifetime_import_energy_counter",
        57722,
        SunSpecValueType.UINT64,
    )

    MAXIMUM_ENERGY = "maximum_energy", 57726, SunSpecValueType.FLOAT32
    AVAILABLE_ENERGY = "available_energy", 57728, SunSpecValueType.FLOAT32

    SOH = "soh", 57730, SunSpecValueType.FLOAT32, True
    SOE = "soe", 57732, SunSpecValueType.FLOAT32, True

    STATUS = "status", 57734, SunSpecValueType.UINT32, True
    STATUS_INTERNAL = "status_internal", 57736, SunSpecValueType.UINT32

    EVENT_LOG = "event_log", 57738, SunSpecValueType.UINT32
    EVENT_LOG_INTERNAL = "event_log_internal", 57746, SunSpecValueType.UINT32

    @staticmethod
    def wordorder() -> str:
        return "little"


class SunSpecBatteryOffset(SunSpecOffset):
    BATTERY0 = "battery0", 0
    BATTERY1 = "battery1", 256


class SunSpecInverterInfoRegister(SunSpecRegister):
    C_ID = "c_id", 40000, SunSpecValueType.STRING, False, 2
    C_DID = "c_did", 40002, SunSpecValueType.UINT16
    C_LENGTH = "c_length", 40003, SunSpecValueType.UINT16
    C_MANUFACTURER = ("c_manufacturer", 40004, SunSpecValueType.STRING, True, 16)
    C_MODEL = "c_model", 40020, SunSpecValueType.STRING, True, 16
    C_VERSION = "c_version", 40044, SunSpecValueType.STRING, True, 8
    C_SERIALNUMBER = ("c_serialnumber", 40052, SunSpecValueType.STRING, True, 16)
    C_DEVICEADDRESS = "c_deviceaddress", 40068, SunSpecValueType.UINT16, True
    C_SUNSPEC_DID = "c_sunspec_did", 40069, SunSpecValueType.UINT16, True
    C_SUNSPEC_LENGTH = "c_sunspec_length", 40070, SunSpecValueType.UINT16

    METER0 = (
        "meter0",
        SunSpecMeterInfoRegister.C_SUNSPEC_DID.address
        + SunSpecMeterOffset.METER0.offset,
        SunSpecMeterInfoRegister.C_SUNSPEC_DID.value_type,
        True,
    )
    METER1 = (
        "meter1",
        SunSpecMeterInfoRegister.C_SUNSPEC_DID.address
        + SunSpecMeterOffset.METER1.offset,
        SunSpecMeterInfoRegister.C_SUNSPEC_DID.value_type,
        True,
    )
    METER2 = (
        "meter2",
        SunSpecMeterInfoRegister.C_SUNSPEC_DID.address
        + SunSpecMeterOffset.METER2.offset,
        SunSpecMeterInfoRegister.C_SUNSPEC_DID.value_type,
        True,
    )

    BATTERY0 = (
        "battery0",
        SunSpecBatteryInfoRegister.C_DEVICEADDRESS.address
        + SunSpecBatteryOffset.BATTERY0.offset,
        SunSpecBatteryInfoRegister.C_DEVICEADDRESS.value_type,
        True,
    )

    BATTERY1 = (
        "battery1",
        SunSpecBatteryInfoRegister.C_DEVICEADDRESS.address
        + SunSpecBatteryOffset.BATTERY1.offset,
        SunSpecBatteryInfoRegister.C_DEVICEADDRESS.value_type,
        True,
    )


class SunSpecInverterRegister(SunSpecRegister):
    CURRENT = "current", 40071, SunSpecValueType.UINT16, True
    L1_CURRENT = "l1_current", 40072, SunSpecValueType.UINT16
    L2_CURRENT = "l2_current", 40073, SunSpecValueType.UINT16
    L3_CURRENT = "l3_current", 40074, SunSpecValueType.UINT16
    CURRENT_SCALE = "current_scale", 40075, SunSpecValueType.INT16, True

    L1_VOLTAGE = "l1_voltage", 40076, SunSpecValueType.UINT16, True
    L2_VOLTAGE = "l2_voltage", 40077, SunSpecValueType.UINT16, True
    L3_VOLTAGE = "l3_voltage", 40078, SunSpecValueType.UINT16, True
    L1N_VOLTAGE = "l1n_voltage", 40079, SunSpecValueType.UINT16, True
    L2N_VOLTAGE = "l2n_voltage", 40080, SunSpecValueType.UINT16, True
    L3N_VOLTAGE = "l3n_voltage", 40081, SunSpecValueType.UINT16, True
    VOLTAGE_SCALE = "voltage_scale", 40082, SunSpecValueType.INT16, True

    POWER_AC = "power_ac", 40083, SunSpecValueType.INT16, True
    POWER_AC_SCALE = "power_ac_scale", 40084, SunSpecValueType.INT16, True

    FREQUENCY = "frequency", 40085, SunSpecValueType.UINT16, True
    FREQUENCY_SCALE = "frequency_scale", 40086, SunSpecValueType.INT16, True

    POWER_APPARENT = "power_apparent", 40087, SunSpecValueType.INT16, True
    POWER_APPARENT_SCALE = "power_apparent_scale", 40088, SunSpecValueType.INT16, True

    POWER_REACTIVE = "power_reactive", 40089, SunSpecValueType.INT16, True
    POWER_REACTIVE_SCALE = (
        "power_reactive_scale",
        40090,
        SunSpecValueType.INT16,
        True,
    )

    POWER_FACTOR = "power_factor", 40091, SunSpecValueType.INT16, True
    POWER_FACTOR_SCALE = "power_factor_scale", 40092, SunSpecValueType.INT16, True

    ENERGY_TOTAL = "energy_total", 40093, SunSpecValueType.UINT32, True
    ENERGY_TOTAL_SCALE = "energy_total_scale", 40095, SunSpecValueType.INT16, True

    CURRENT_DC = "current_dc", 40096, SunSpecValueType.UINT16, True
    CURRENT_DC_SCALE = "current_dc_scale", 40097, SunSpecValueType.INT16, True

    VOLTAGE_DC = "voltage_dc", 40098, SunSpecValueType.UINT16, True
    VOLTAGE_DC_SCALE = "voltage_dc_scale", 40099, SunSpecValueType.INT16, True

    POWER_DC = "power_dc", 40100, SunSpecValueType.INT16, True
    POWER_DC_SCALE = "power_dc_scale", 40101, SunSpecValueType.INT16, True

    TEMPERATURE = "temperature", 40103, SunSpecValueType.INT16, True
    TEMPERATURE_SCALE = "temperature_scale", 40106, SunSpecValueType.INT16, True

    STATUS = "status", 40107, SunSpecValueType.UINT16, True
    VENDOR_STATUS = "vendor_status", 40108, SunSpecValueType.UINT16

    RRCR_STATE = "rrcr_state", 61440, SunSpecValueType.UINT16
    ACTIVE_POWER_LIMIT = "active_power_limit", 61441, SunSpecValueType.UINT16
    COSPHI = "cosphi", 61442, SunSpecValueType.FLOAT32

    COMMIT_POWER_CONTROL_SETTINGS = (
        "commit_power_control_settings",
        61696,
        SunSpecValueType.INT16,
    )
    RESTORE_POWER_CONTROL_SETTINGS = (
        "restore_power_control_settings",
        61697,
        SunSpecValueType.INT16,
    )

    REACTIVE_POWER_CONFIG = "reactive_power_config", 61699, SunSpecValueType.INT32
    REACTIVE_POWER_RESPONSE_TIME = (
        "reactive_power_response_time",
        61701,
        SunSpecValueType.UINT32,
    )

    ADVANCED_POWER_CONTROL_ENABLE = (
        "advanced_power_control_enable",
        61762,
        SunSpecValueType.UINT16,
    )

    EXPORT_CONTROL_MODE = "export_control_mode", 63232, SunSpecValueType.UINT16
    EXPORT_CONTROL_LIMIT_MODE = (
        "export_control_limit_mode",
        63233,
        SunSpecValueType.UINT16,
    )
    EXPORT_CONTROL_SITE_LIMIT = (
        "export_control_site_limit",
        63234,
        SunSpecValueType.FLOAT32,
    )

class SunSpecGridStatusRegister(SunSpecRegister):
    GRID_STATUS = "grid_status", 40113, SunSpecValueType.UINT32, True
