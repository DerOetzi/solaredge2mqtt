from pydantic import BaseModel


class PowerFlow(BaseModel):
    pv_production: int
    inverter: int
    inverter_consumption: int
    inverter_delivery: int
    house_consumption: int
    grid: int
    grid_consumption: int
    grid_delivery: int
    battery: int
    battery_charge: int
    battery_discharge: int
