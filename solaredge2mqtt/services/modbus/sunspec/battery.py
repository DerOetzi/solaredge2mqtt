from solaredge2mqtt.services.modbus.sunspec.base import SunSpecOffset, SunSpecRegister
from solaredge2mqtt.services.modbus.sunspec.values import (
    SunSpecPayload,
    SunSpecValueType,
)


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


class SunSpecStorageControlRegister(SunSpecRegister):
    """Storage control registers for battery management.

    These registers allow control of battery charge/discharge behavior.
    Based on SolarEdge Modbus protocol documentation.
    Register addresses starting at 57348.
    """

    CONTROL_MODE = "control_mode", 57348, SunSpecValueType.UINT16, True
    AC_CHARGE_POLICY = "ac_charge_policy", 57349, SunSpecValueType.UINT16, True
    AC_CHARGE_LIMIT = "ac_charge_limit", 57350, SunSpecValueType.FLOAT32, True
    BACKUP_RESERVE = "backup_reserve", 57352, SunSpecValueType.FLOAT32, True
    DEFAULT_MODE = "default_mode", 57354, SunSpecValueType.UINT16, True
    COMMAND_TIMEOUT = "command_timeout", 57355, SunSpecValueType.UINT32, True
    COMMAND_MODE = "command_mode", 57357, SunSpecValueType.UINT16, True
    CHARGE_LIMIT = "charge_limit", 57358, SunSpecValueType.FLOAT32, True
    DISCHARGE_LIMIT = "discharge_limit", 57360, SunSpecValueType.FLOAT32, True

    def decode_response(
        self, registers: list[int], data: dict[str, SunSpecPayload]
    ) -> dict[str, SunSpecPayload]:
        data = super().decode_response(registers, data)

        # Handle not implemented values
        if self == SunSpecStorageControlRegister.CONTROL_MODE:
            if data[self.identifier] == SunSpecValueType.UINT16.not_implemented_value:
                data[self.identifier] = None
        elif self in (
            SunSpecStorageControlRegister.AC_CHARGE_LIMIT,
            SunSpecStorageControlRegister.BACKUP_RESERVE,
            SunSpecStorageControlRegister.CHARGE_LIMIT,
            SunSpecStorageControlRegister.DISCHARGE_LIMIT,
        ):
            if data[self.identifier] == SunSpecValueType.FLOAT32.not_implemented_value:
                data[self.identifier] = None
            elif data[self.identifier] < 0:
                data[self.identifier] = None

        return data

    @staticmethod
    def wordorder() -> str:
        return "little"
