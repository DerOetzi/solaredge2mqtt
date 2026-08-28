from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.storage.models import Point, canonical_tags
from solaredge2mqtt.core.storage.periods import from_epoch, hour_start
from solaredge2mqtt.core.storage.queries import (
    AGGREGATE_ENERGY,
    AGGREGATE_MINMAXMEAN_BATTERY,
    AGGREGATE_MINMAXMEAN_POWERFLOW,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.storage import StorageService

AGGREGATION_LOOKBACK_HOURS = 2

AGGREGATION_TYPES = (("min", "agg_min"), ("max", "agg_max"), ("mean", "agg_mean"))

RAW_TO_AGGREGATED = {
    "powerflow_raw": ("powerflow", AGGREGATE_MINMAXMEAN_POWERFLOW),
    "battery_raw": ("battery", AGGREGATE_MINMAXMEAN_BATTERY),
}

MONEY_FROM_CONSUMPTION = {
    "consumer_used_production": ("money_saved", "money_price_in"),
    "grid_consumption": ("money_consumed", None),
}

MONEY_FROM_DELIVERY = {"grid_delivery": ("money_delivered", "money_price_out")}


class PointCollector:
    def __init__(self) -> None:
        self._points: dict[tuple[str, str, int], Point] = {}

    def add(
        self,
        measurement: str,
        tags: dict[str, str],
        timestamp: int,
        field: str,
        value: float,
    ) -> None:
        key = (measurement, canonical_tags(tags), timestamp)

        if key not in self._points:
            point = Point(measurement).time(from_epoch(timestamp))
            for tag_key, tag_value in tags.items():
                point.tag(tag_key, tag_value)
            self._points[key] = point

        self._points[key].field(field, value)

    @property
    def points(self) -> list[Point]:
        return list(self._points.values())


def _tags(unit: Any, agg_type: str | None = None) -> dict[str, str]:
    tags: dict[str, str] = {}
    if unit is not None:
        tags["unit"] = str(unit)
    if agg_type is not None:
        tags["agg_type"] = agg_type

    return tags


async def aggregate(
    storage: StorageService, now: datetime | None = None
) -> list[Point]:
    moment = now or datetime.now(tz=timezone.utc)
    start = int(
        (hour_start(moment) - timedelta(hours=AGGREGATION_LOOKBACK_HOURS)).timestamp()
    )

    collector = PointCollector()

    for raw_measurement, (measurement, query) in RAW_TO_AGGREGATED.items():
        rows = await storage.fetch_all(query, {"start": start})
        logger.debug(f"Aggregating {len(rows)} buckets of {raw_measurement}")

        for row in rows:
            for agg_type, column in AGGREGATION_TYPES:
                collector.add(
                    measurement,
                    _tags(row["unit"], agg_type),
                    int(row["bucket"]),
                    str(row["field"]),
                    float(row[column]),
                )

    energy_rows = await storage.fetch_all(AGGREGATE_ENERGY, {"start": start})
    logger.debug(f"Aggregating {len(energy_rows)} energy buckets")

    for row in energy_rows:
        _collect_energy(collector, storage, row)

    points = collector.points
    await storage.write_points(points)

    return points


def _collect_energy(
    collector: PointCollector, storage: StorageService, row: Any
) -> None:
    field = str(row["field"])
    energy = float(row["energy_kwh"])
    tags = _tags(row["unit"])
    bucket = int(row["bucket"])

    collector.add("energy", tags, bucket, field, energy)

    price_in = storage.prices.price_in
    price_out = storage.prices.price_out

    for mapping, price in (
        (MONEY_FROM_CONSUMPTION, price_in),
        (MONEY_FROM_DELIVERY, price_out),
    ):
        if field not in mapping:
            continue

        money_field, price_field = mapping[field]
        collector.add("energy", tags, bucket, money_field, energy * price)
        if price_field is not None:
            collector.add("energy", tags, bucket, price_field, price)
