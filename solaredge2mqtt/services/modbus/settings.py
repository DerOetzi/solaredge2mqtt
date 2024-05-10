from pydantic import BaseModel, Field


class ModbusSettings(BaseModel):
    host: str
    port: int = Field(1502)
    timeout: int = Field(1)
    unit: int = Field(1)
