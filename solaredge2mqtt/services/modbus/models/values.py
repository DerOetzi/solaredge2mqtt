from pydantic import Field

from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.models import ComponentValueGroup


class ModbusACCurrent(ComponentValueGroup):
    actual: float = Field(**HASensor.CURRENT_A.field("actual"))
    l1: float | None = Field(None, **HASensor.CURRENT_A.field("L1"))
    l2: float | None = Field(None, **HASensor.CURRENT_A.field("L2"))
    l3: float | None = Field(None, **HASensor.CURRENT_A.field("L3"))

    def __init__(self, data: dict[str, str | int]):
        values = {"actual": self.scale_value(data, "current")}

        for phase in ["l1", "l2", "l3"]:
            if f"{phase}_current" in data:
                values[phase] = self.scale_value(
                    data, f"{phase}_current", "current_scale"
                )

        super().__init__(**values)


class ModbusACVoltage(ComponentValueGroup):
    l1: float | None = Field(None, **HASensor.VOLTAGE_V.field("L1"))
    l2: float | None = Field(None, **HASensor.VOLTAGE_V.field("L2"))
    l3: float | None = Field(None, **HASensor.VOLTAGE_V.field("L3"))
    l1n: float | None = Field(None, **HASensor.VOLTAGE_V.field("L1N"))
    l2n: float | None = Field(None, **HASensor.VOLTAGE_V.field("L2N"))
    l3n: float | None = Field(None, **HASensor.VOLTAGE_V.field("L3N"))

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


class ModbusACPower(ComponentValueGroup):
    actual: float = Field(**HASensor.POWER_W.field("actual"))
    reactive: float = Field(**HASensor.REACTIVE_POWER.field("reactive"))
    apparent: float = Field(**HASensor.APPARENT_POWER.field("apparent"))
    factor: float = Field(**HASensor.POWER_FACTOR.field("power factor"))

    def __init__(self, data: dict[str, str | int], power_key: str):
        actual = self.scale_value(data, power_key)
        reactive = self.scale_value(data, "power_reactive")
        apparent = self.scale_value(data, "power_apparent")
        factor = self.scale_value(data, "power_factor")
        super().__init__(
            actual=actual, reactive=reactive, apparent=apparent, factor=factor
        )


class ModbusAC(ComponentValueGroup):
    current: ModbusACCurrent = Field(title="Current")
    voltage: ModbusACVoltage = Field(title="Voltage")
    power: ModbusACPower = Field(title="Power")
    frequency: float = Field(**HASensor.FREQUENCY_HZ.field("Grid frequency"))

    def __init__(self, data: dict[str, str | int]):
        current = ModbusACCurrent(data)
        voltage = ModbusACVoltage(data)
        power = ModbusACPower(data, "power_ac")
        frequency = self.scale_value(data, "frequency")

        super().__init__(
            current=current, voltage=voltage, power=power, frequency=frequency
        )


class ModbusEnergy(ComponentValueGroup):
    totalexport: float = Field(**HASensor.ENERGY_WH.field("Export"))
    totalimport: float = Field(**HASensor.ENERGY_WH.field("Import"))

    def __init__(self, data: dict[str, str | int]):
        super().__init__(
            totalexport=self.scale_value(
                data, "export_energy_active", "energy_active_scale"
            ),
            totalimport=self.scale_value(
                data, "import_energy_active", "energy_active_scale"
            ),
        )


class ModbusDC(ComponentValueGroup):
    current: float = Field(**HASensor.CURRENT_A.field("current"))
    voltage: float = Field(**HASensor.VOLTAGE_V.field("voltage"))
    power: float = Field(**HASensor.POWER_W.field("power"))

    def __init__(self, data: dict[str, str | int]):
        super().__init__(
            current=self.scale_value(data, "current_dc"),
            voltage=self.scale_value(data, "voltage_dc"),
            power=self.scale_value(data, "power_dc"),
        )
