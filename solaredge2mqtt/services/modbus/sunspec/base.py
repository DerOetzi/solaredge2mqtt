from __future__ import annotations

from pymodbus.client import ModbusTcpClient

from solaredge2mqtt.core.models import EnumModel
from solaredge2mqtt.services.modbus.sunspec.values import (
    SunSpecInputData,
    SunSpecPayload,
    SunSpecValueType,
)


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
            response_slice = registers[offset: offset + register.length]
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

    def encode_request(self, value: SunSpecInputData) -> list[int]:
        if isinstance(value, bool):
            value = 1 if value else 0

        value = ModbusTcpClient.convert_to_registers(
            value, self.value_type.data_type, word_order=self.wordorder()
        )

        return value


class SunSpecOffset(EnumModel):
    def __init__(self, identifier: str, offset: int):
        # pylint: disable=super-init-not-called
        self._identifier = identifier
        self._offset = offset

    @property
    def idx(self) -> int:
        return int(self._identifier[-1])

    @property
    def identifier(self) -> str:
        return self._identifier

    @property
    def offset(self) -> int:
        return self._offset
