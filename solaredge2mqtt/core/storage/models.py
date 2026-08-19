from __future__ import annotations

from datetime import datetime, timezone
from typing import Self

FieldValue = float | int | str | bool


def canonical_tags(tags: dict[str, str]) -> str:
    return ",".join(f"{key}={tags[key]}" for key in sorted(tags))


class Point:
    __slots__ = ("measurement", "fields", "tags", "timestamp")

    def __init__(self, measurement: str) -> None:
        self.measurement: str = measurement
        self.fields: dict[str, FieldValue] = {}
        self.tags: dict[str, str] = {}
        self.timestamp: datetime | None = None

    def field(self, key: str, value: FieldValue) -> Self:
        self.fields[key] = value
        return self

    def tag(self, key: str, value: str) -> Self:
        self.tags[key] = value
        return self

    def time(self, value: datetime) -> Self:
        self.timestamp = value
        return self

    @property
    def tags_canonical(self) -> str:
        return canonical_tags(self.tags)

    def epoch_seconds(self) -> int:
        moment = self.timestamp or datetime.now(tz=timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)

        return int(moment.timestamp())

    def __repr__(self) -> str:
        return (
            f"Point(measurement={self.measurement!r}, tags={self.tags!r}, "
            f"fields={self.fields!r}, timestamp={self.timestamp!r})"
        )
