from __future__ import annotations

from pydantic import BaseModel, Field


class PowerflowSettings(BaseModel):
    external_production: bool = Field(default=False)
    retain: bool = Field(default=False)
