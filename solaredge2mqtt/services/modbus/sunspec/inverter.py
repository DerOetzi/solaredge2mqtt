from solaredge2mqtt.services.modbus.sunspec.base import SunSpecRegister
from solaredge2mqtt.services.modbus.sunspec.battery import (
    SunSpecBatteryInfoRegister,
    SunSpecBatteryOffset,
)
from solaredge2mqtt.services.modbus.sunspec.meter import (
    SunSpecMeterInfoRegister,
    SunSpecMeterOffset,
)
from solaredge2mqtt.services.modbus.sunspec.values import (
    SunSpecPayload,
    SunSpecValueType,
)


class SunSpecInverterInfoRegister(SunSpecRegister):
    C_ID = "c_id", 40000, SunSpecValueType.STRING, False, 2
    C_DID = "c_did", 40002, SunSpecValueType.UINT16
    C_LENGTH = "c_length", 40003, SunSpecValueType.UINT16
    C_MANUFACTURER = ("c_manufacturer", 40004,
                      SunSpecValueType.STRING, True, 16)
    C_MODEL = "c_model", 40020, SunSpecValueType.STRING, True, 16
    C_VERSION = "c_version", 40044, SunSpecValueType.STRING, True, 8
    C_SERIALNUMBER = ("c_serialnumber", 40052,
                      SunSpecValueType.STRING, True, 16)
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


class SunSpecGridStatusRegister(SunSpecRegister):
    GRID_STATUS = "grid_status", 40113, SunSpecValueType.UINT32, True


class SunSpecPowerControlRegister(SunSpecRegister):
    RRCR_STATE = "rrcr_state", 61440, SunSpecValueType.UINT16, True
    ACTIVE_POWER_LIMIT = "active_power_limit", 61441, SunSpecValueType.UINT16, True
    COSPHI = "cosphi", 61442, SunSpecValueType.FLOAT32, False

    COMMIT_POWER_CONTROL_SETTINGS = (
        "commit_power_control_settings",
        61696,
        SunSpecValueType.INT16,
        True
    )
    RESTORE_POWER_CONTROL_SETTINGS = (
        "restore_power_control_settings",
        61697,
        SunSpecValueType.INT16,
        True
    )

    ADVANCED_POWER_CONTROL_ENABLE = (
        "advanced_power_control_enable",
        61762,
        SunSpecValueType.INT32,
        True
    )

    REACTIVE_POWER_CONFIG = "reactive_power_config", 61700, SunSpecValueType.INT32, True
    REACTIVE_POWER_RESPONSE_TIME = (
        "reactive_power_response_time",
        61702,
        SunSpecValueType.UINT32, True
    )

    def decode_response(
        self, registers: list[int], data: dict[str, SunSpecPayload]
    ) -> dict[str, SunSpecPayload]:
        data = super().decode_response(registers, data)

        if self == SunSpecPowerControlRegister.ADVANCED_POWER_CONTROL_ENABLE:
            data[self.identifier] = data[self.identifier] == 1

        return data

    @staticmethod
    def wordorder() -> str:
        return "little"


class SunSpecSiteLimitRegister(SunSpecRegister):
    EXPORT_CONTROL_MODE = "export_control_mode", 57344, SunSpecValueType.UINT16, True
    EXPORT_CONTROL_LIMIT_MODE = (
        "export_control_limit_mode",
        57345,
        SunSpecValueType.UINT16,
        True
    )
    EXPORT_CONTROL_SITE_LIMIT = (
        "export_control_site_limit",
        57346,
        SunSpecValueType.FLOAT32,
        True
    )

    def decode_response(
        self, registers: list[int], data: dict[str, SunSpecPayload]
    ) -> dict[str, SunSpecPayload]:
        data = super().decode_response(registers, data)

        if self == SunSpecPowerControlRegister.EXPORT_CONTROL_SITE_LIMIT:
            data[self.identifier] = 0 if data[self.identifier] < 0 else int(
                data[self.identifier])
        elif self == SunSpecPowerControlRegister.EXPORT_CONTROL_MODE:
            bitmask = data[self.identifier]
            data[f"{self.identifier}_raw"] = bitmask

            data[self.identifier] = ((bitmask & 0x0001) +
                                     ((bitmask & 0x0002) >> 1) +
                                     ((bitmask & 0x0004) >> 2))

            data["export_control_external_production"] = bool(bitmask & 0x0400)
            data["export_control_negative_site_limit"] = bool(bitmask & 0x0800)

        return data

    @staticmethod
    def wordorder() -> str:
        return "little"
