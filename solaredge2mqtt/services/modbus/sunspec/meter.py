from solaredge2mqtt.services.modbus.sunspec.base import SunSpecOffset, SunSpecRegister
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecValueType


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
