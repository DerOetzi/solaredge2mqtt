from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Self

from pydantic import Field

from solaredge2mqtt.core.models import Solaredge2MQTTBaseModel
from solaredge2mqtt.services.homeassistant.models import (
    HomeAssistantSensorType as HASensor,
)
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecPayload


class MixinModbusSunSpecScaleValue:
    @staticmethod
    def scale_value(
        data: SunSpecPayload,
        value_key: str,
        scale_key: str | None = None,
        digits: int = 2,
    ) -> float:
        if scale_key is None:
            scale_key = f"{value_key}_scale"

        value = int(data[value_key])
        scale = int(data[scale_key])

        return round(value * 10**scale, digits)


class ModbusComponentValueGroup(
    Solaredge2MQTTBaseModel, MixinModbusSunSpecScaleValue, ABC
):
    @classmethod
    def from_sunspec(cls, payload: SunSpecPayload) -> Self:
        return cls(**cls.extract_sunspec_payload(payload))

    @classmethod
    @abstractmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        pass  # pragma: no cover


class ModbusAC(ModbusComponentValueGroup):
    current: ModbusACCurrent = Field(title="Current")
    voltage: ModbusACVoltage = Field(title="Voltage")
    power: ModbusACPower = Field(title="Power")
    frequency: float = Field(**HASensor.FREQUENCY_HZ.field("Grid frequency"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, Any]:
        return {
            "current": ModbusACCurrent.extract_sunspec_payload(payload),
            "voltage": ModbusACVoltage.extract_sunspec_payload(payload),
            "power": ModbusACPower.parse_sunspec_payload_power_key(payload, "power_ac"),
            "frequency": cls.scale_value(payload, "frequency"),
        }


class ModbusACCurrent(ModbusComponentValueGroup):
    actual: float = Field(**HASensor.CURRENT_A.field("actual"))
    l1: float | None = Field(default=None, **HASensor.CURRENT_A.field("L1"))
    l2: float | None = Field(default=None, **HASensor.CURRENT_A.field("L2"))
    l3: float | None = Field(default=None, **HASensor.CURRENT_A.field("L3"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, float]:
        values = {
            "actual": cls.scale_value(payload, "current"),
        }

        for phase in ["l1", "l2", "l3"]:
            current_key = f"{phase}_current"
            if current_key in payload:
                values[phase] = cls.scale_value(payload, current_key, "current_scale")

        return values


class ModbusACVoltage(ModbusComponentValueGroup):
    l1: float | None = Field(default=None, **HASensor.VOLTAGE_V.field("L1"))
    l2: float | None = Field(default=None, **HASensor.VOLTAGE_V.field("L2"))
    l3: float | None = Field(default=None, **HASensor.VOLTAGE_V.field("L3"))
    l1n: float | None = Field(default=None, **HASensor.VOLTAGE_V.field("L1N"))
    l2n: float | None = Field(default=None, **HASensor.VOLTAGE_V.field("L2N"))
    l3n: float | None = Field(default=None, **HASensor.VOLTAGE_V.field("L3N"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, float]:
        values: dict[str, float] = {}

        for phase in ["l1", "l2", "l3"]:
            voltage_key = f"{phase}_voltage"
            if voltage_key in payload:
                values[phase] = cls.scale_value(payload, voltage_key, "voltage_scale")

            voltage_n_key = f"{phase}n_voltage"

            if voltage_n_key in payload:
                values[f"{phase}n"] = cls.scale_value(
                    payload, voltage_n_key, "voltage_scale"
                )

        return values


class ModbusACPower(ModbusComponentValueGroup):
    actual: float = Field(**HASensor.POWER_W.field("actual"))
    reactive: float = Field(**HASensor.REACTIVE_POWER.field("reactive"))
    apparent: float = Field(**HASensor.APPARENT_POWER.field("apparent"))
    factor: float = Field(**HASensor.POWER_FACTOR.field("power factor"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, float]:
        return cls.parse_sunspec_payload_power_key(payload, "power_ac")

    @classmethod
    def parse_sunspec_payload_power_key(
        cls, payload: SunSpecPayload, power_key: Literal["power_ac", "power"]
    ) -> dict[str, float]:
        return {
            "actual": cls.scale_value(payload, power_key),
            "reactive": cls.scale_value(payload, "power_reactive"),
            "apparent": cls.scale_value(payload, "power_apparent"),
            "factor": cls.scale_value(payload, "power_factor"),
        }


class ModbusEnergy(ModbusComponentValueGroup):
    totalexport: float = Field(**HASensor.ENERGY_WH.field("Export"))
    totalimport: float = Field(**HASensor.ENERGY_WH.field("Import"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, float]:
        return {
            "totalexport": cls.scale_value(
                payload, "export_energy_active", "energy_active_scale"
            ),
            "totalimport": cls.scale_value(
                payload, "import_energy_active", "energy_active_scale"
            ),
        }


class ModbusDC(ModbusComponentValueGroup):
    current: float = Field(**HASensor.CURRENT_A.field("current"))
    voltage: float = Field(**HASensor.VOLTAGE_V.field("voltage"))
    power: float = Field(**HASensor.POWER_W.field("power"))

    @classmethod
    def extract_sunspec_payload(cls, payload: SunSpecPayload) -> dict[str, float]:
        return {
            "current": cls.scale_value(payload, "current_dc"),
            "voltage": cls.scale_value(payload, "voltage_dc"),
            "power": cls.scale_value(payload, "power_dc"),
        }
