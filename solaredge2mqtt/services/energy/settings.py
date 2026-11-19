from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

WEEKDAYS: tuple[Weekday, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

SLOT_MINUTES = 15

MINUTES_PER_DAY = 24 * 60


def to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


class PriceScheduleEntry(BaseModel):
    name: str | None = Field(default=None)
    months: list[int] = Field(default_factory=list)
    weekdays: list[Weekday] = Field(default_factory=list)
    start: str = Field(default="00:00")
    end: str = Field(default="24:00")
    consumption: float | None = Field(default=None)
    delivery: float | None = Field(default=None)

    @field_validator("months")
    @classmethod
    def validate_months(cls, months: list[int]) -> list[int]:
        for month in months:
            if not 1 <= month <= 12:
                raise ValueError(f"Month {month} is not between 1 and 12")

        return months

    @field_validator("start", "end", mode="before")
    @classmethod
    def minutes_to_time(cls, value: object) -> object:
        if isinstance(value, int) and not isinstance(value, bool):
            return f"{value // 60}:{value % 60:02d}"

        return value

    @field_validator("start", "end")
    @classmethod
    def validate_time(cls, value: str, info: ValidationInfo) -> str:
        try:
            hours, minutes = (int(part) for part in value.split(":"))
        except ValueError:
            raise ValueError(f"Time {value} is not in the format HH:MM") from None

        latest = MINUTES_PER_DAY if info.field_name == "end" else MINUTES_PER_DAY - 1
        total = hours * 60 + minutes
        if not 0 <= minutes < 60 or not 0 <= total <= latest:
            raise ValueError(f"Time {value} is out of range for {info.field_name}")

        if minutes % SLOT_MINUTES:
            raise ValueError(f"Time {value} is not on a quarter hour")

        return f"{hours:02d}:{minutes:02d}"

    @property
    def start_minute(self) -> int:
        return to_minutes(self.start)

    @property
    def end_minute(self) -> int:
        return to_minutes(self.end)

    @property
    def wraps_midnight(self) -> bool:
        return self.end_minute <= self.start_minute


class PriceSettings(BaseModel):
    consumption: float | None = Field(default=None)
    delivery: float | None = Field(default=None)
    currency: str | None = Field(default=None)
    schedule: list[PriceScheduleEntry] = Field(default_factory=list)

    @property
    def is_configured(self) -> bool:
        return self.is_consumption_configured or self.is_delivery_configured

    @property
    def is_consumption_configured(self) -> bool:
        return self.currency is not None and (
            self.consumption is not None
            or any(entry.consumption is not None for entry in self.schedule)
        )

    @property
    def is_delivery_configured(self) -> bool:
        return self.currency is not None and (
            self.delivery is not None
            or any(entry.delivery is not None for entry in self.schedule)
        )

    @property
    def price_in(self) -> float:
        return self.consumption or 0.0

    @property
    def price_out(self) -> float:
        return self.delivery or 0.0


class EnergySettings(BaseModel):
    retain: bool = Field(default=False)
