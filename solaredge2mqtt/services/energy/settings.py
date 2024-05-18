from pydantic import BaseModel, Field


class PriceSettings(BaseModel):
    consumption: float = Field(None)
    delivery: float = Field(None)
    currency: str = Field(None)

    @property
    def is_configured(self) -> bool:
        return self.is_consumption_configured or self.is_delivery_configured

    @property
    def is_consumption_configured(self) -> bool:
        return self.consumption is not None and self.currency is not None

    @property
    def is_delivery_configured(self) -> bool:
        return self.delivery is not None and self.currency is not None

    @property
    def price_in(self) -> float:
        return self.consumption or 0.0

    @property
    def price_out(self) -> float:
        return self.delivery or 0.0
