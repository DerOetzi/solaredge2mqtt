from solaredge2mqtt.services.events import ComponentEvent, ComponentsEvent


class ModbusInverterReadEvent(ComponentEvent):
    pass


class ModbusMetersReadEvent(ComponentsEvent):
    pass


class ModbusBatteriesReadEvent(ComponentsEvent):
    pass
