from solaredge2mqtt.core.events.events import BaseEvent
from solaredge2mqtt.services.events import ComponentEvent, ComponentsEvent
from solaredge2mqtt.services.modbus.sunspec.base import SunSpecRegister
from solaredge2mqtt.services.modbus.sunspec.values import SunSpecInputData


class ModbusInverterReadEvent(ComponentEvent):
    pass


class ModbusMetersReadEvent(ComponentsEvent):
    pass


class ModbusBatteriesReadEvent(ComponentsEvent):
    pass


class ModbusWriteEvent(BaseEvent):
    AWAIT = True

    def __init__(self,
                 register: SunSpecRegister,
                 payload: SunSpecInputData):
        self._register = register
        self._payload = payload

    @property
    def register(self) -> SunSpecRegister:
        return self._register

    @property
    def payload(self) -> SunSpecInputData:
        return self._payload
