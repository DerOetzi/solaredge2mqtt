from solaredge2mqtt.services.modbus.sunspec.base import SunSpecOffset, SunSpecRegister
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecValueType


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
