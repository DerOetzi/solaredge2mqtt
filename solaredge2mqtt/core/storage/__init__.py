from __future__ import annotations

from asyncio import Lock
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import aiosqlite
from tzlocal import get_localzone_name

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.storage.aggregation import aggregate
from solaredge2mqtt.core.storage.connection import (
    open_read_connection,
    open_write_connection,
)
from solaredge2mqtt.core.storage.events import (
    StorageAggregatedEvent,
    StorageOfflineEvent,
    StorageOnlineEvent,
)
from solaredge2mqtt.core.storage.models import Point
from solaredge2mqtt.core.storage.periods import (
    as_epoch,
    day_bounds,
    from_epoch,
    hour_start,
    period_bounds,
)
from solaredge2mqtt.core.storage.queries import (
    PERIOD_SUM,
    PIVOT_BY_TIME,
    PRODUCTION_LAST_HOUR,
)
from solaredge2mqtt.core.storage.retention import (
    apply_raw_retention,
    maybe_apply_long_retention,
)
from solaredge2mqtt.core.storage.schema import migrate
from solaredge2mqtt.core.storage.settings import StorageSettings
from solaredge2mqtt.core.timer.events import Interval10MinTriggerEvent

if TYPE_CHECKING:
    from solaredge2mqtt.services.energy.models import HistoricPeriod
    from solaredge2mqtt.services.energy.settings import PriceSettings

LOCAL_TZ = ZoneInfo(get_localzone_name())

__all__ = ["Point", "StorageService"]

INSERT_SERIES = """
INSERT INTO series (measurement, field, tags) VALUES (?, ?, ?)
ON CONFLICT (measurement, field, tags) DO NOTHING
"""

SELECT_SERIES = """
SELECT series_id FROM series WHERE measurement = ? AND field = ? AND tags = ?
"""

INSERT_SERIES_TAG = """
INSERT INTO series_tag (series_id, tag_key, tag_value) VALUES (?, ?, ?)
ON CONFLICT (series_id, tag_key) DO UPDATE SET tag_value = excluded.tag_value
"""

UPSERT_POINT = """
INSERT INTO point (series_id, ts, value) VALUES (?, ?, ?)
ON CONFLICT (series_id, ts) DO UPDATE SET value = excluded.value
"""

SELECT_META = "SELECT value FROM meta WHERE key = ?"

UPSERT_META = """
INSERT INTO meta (key, value) VALUES (?, ?)
ON CONFLICT (key) DO UPDATE SET value = excluded.value
"""


class StorageService:
    def __init__(
        self,
        settings: StorageSettings,
        prices: PriceSettings,
        config_dir: str = "config",
    ) -> None:
        self.settings: StorageSettings = settings
        self.prices: PriceSettings = prices
        self.db_path: Path = settings.resolve_path(config_dir)

        self._write: aiosqlite.Connection | None = None
        self._read: aiosqlite.Connection | None = None
        self._write_lock: Lock = Lock()
        self._series_cache: dict[tuple[str, str, str], int] = {}

        EventBus.register(self)

    async def async_init(self) -> None:
        logger.info(f"Using storage database '{self.db_path}'")

        self._write = await open_write_connection(self.db_path)
        await migrate(self._write)
        self._read = await open_read_connection(self.db_path)

    async def set_online(self) -> None:
        await EventBus.emit(StorageOnlineEvent(self.settings.debounce_cycles))

    @property
    def write_connection(self) -> aiosqlite.Connection:
        if self._write is None:
            raise RuntimeError("Storage database not initialized")

        return self._write

    @property
    def read_connection(self) -> aiosqlite.Connection:
        if self._read is None:
            raise RuntimeError("Storage database not initialized")

        return self._read

    async def write_point(self, point: Point) -> None:
        await self.write_points([point])

    async def write_points(self, points: list[Point]) -> None:
        if not points:
            return

        try:
            async with self._write_lock:
                rows = [
                    (
                        await self._series_id(
                            point.measurement, field, point.tags_canonical, point.tags
                        ),
                        point.epoch_seconds(),
                        value,
                    )
                    for point in points
                    for field, value in point.fields.items()
                ]

                await self.write_connection.execute("BEGIN")
                await self.write_connection.executemany(UPSERT_POINT, rows)
                await self.write_connection.execute("COMMIT")

            await EventBus.emit(StorageOnlineEvent())
        except Exception:
            await EventBus.emit(StorageOfflineEvent())
            raise

    async def _series_id(
        self, measurement: str, field: str, tags_key: str, tags: dict[str, str]
    ) -> int:
        cache_key = (measurement, field, tags_key)
        if cache_key in self._series_cache:
            return self._series_cache[cache_key]

        await self.write_connection.execute(
            INSERT_SERIES, (measurement, field, tags_key)
        )

        async with self.write_connection.execute(
            SELECT_SERIES, (measurement, field, tags_key)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            raise RuntimeError(
                f"Could not resolve series for {measurement}.{field} [{tags_key}]"
            )

        series_id = int(row[0])

        for tag_key, tag_value in tags.items():
            await self.write_connection.execute(
                INSERT_SERIES_TAG, (series_id, tag_key, tag_value)
            )

        self._series_cache[cache_key] = series_id
        return series_id

    @EventBus.subscribe(Interval10MinTriggerEvent)
    async def loop(self, event: Interval10MinTriggerEvent) -> None:
        logger.info("Aggregate powerflow and energy raw data")
        await aggregate(self)

        logger.info("Apply retention on raw data")
        await apply_raw_retention(self)
        await maybe_apply_long_retention(self)

        await EventBus.emit(StorageAggregatedEvent())

    async def query_timeunit(
        self, period: HistoricPeriod, measurement: str
    ) -> list[dict[str, Any]] | None:
        start, stop = period_bounds(period, datetime.now(tz=timezone.utc), LOCAL_TZ)

        rows = await self.fetch_all(
            PERIOD_SUM,
            {
                "measurement": measurement,
                "start": as_epoch(start),
                "stop": as_epoch(stop),
            },
        )

        if not rows:
            return None

        records: dict[str | None, dict[str, Any]] = {}
        for row in rows:
            unit = row["unit"]
            if unit not in records:
                records[unit] = {"_start": start, "_stop": stop}
                if unit is not None:
                    records[unit]["unit"] = unit

            records[unit][str(row["field"])] = row["value"]

        return list(records.values())

    async def query_production_last_hour(
        self, now: datetime | None = None
    ) -> dict[str, Any] | None:
        stop = hour_start(now or datetime.now(tz=timezone.utc))
        start = stop - timedelta(hours=1)

        rows = await self.fetch_all(
            PRODUCTION_LAST_HOUR,
            {"start": as_epoch(start), "stop": as_epoch(stop)},
        )

        if not rows:
            return None

        row = rows[0]
        return {
            "_time": from_epoch(int(row["ts"])),
            "energy": row["energy"],
            "power": row["power"],
        }

    async def query_pivot(
        self, measurement: str, start: int, stop: int | None = None
    ) -> list[dict[str, Any]]:
        rows = await self.fetch_all(
            PIVOT_BY_TIME,
            {"measurement": measurement, "start": start, "stop": stop},
        )

        records: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        current_ts: int | None = None

        for row in rows:
            timestamp = int(row["ts"])
            if current is None or timestamp != current_ts:
                current = {"_time": from_epoch(timestamp)}
                current_ts = timestamp
                records.append(current)

            current[str(row["field"])] = row["value"]

        return records

    async def query_days(
        self, measurement: str, days: int, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        start, stop = day_bounds(now or datetime.now(tz=timezone.utc), LOCAL_TZ, days)
        return await self.query_pivot(measurement, as_epoch(start), as_epoch(stop))

    async def execute_write(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> int:
        try:
            async with self._write_lock:
                cursor = await self.write_connection.execute(query, parameters or {})
                rowcount = cursor.rowcount
                await cursor.close()

            return max(rowcount, 0)
        except Exception:
            await EventBus.emit(StorageOfflineEvent())
            raise

    async def all_series_ids(self) -> list[int]:
        rows = await self.fetch_all("SELECT series_id FROM series")
        return [int(row[0]) for row in rows]

    async def series_ids(self, measurement: str) -> list[int]:
        async with self.read_connection.execute(
            "SELECT series_id FROM series WHERE measurement = ?", (measurement,)
        ) as cursor:
            rows = await cursor.fetchall()

        return [int(row[0]) for row in rows]

    async def fetch_all(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[aiosqlite.Row]:
        try:
            async with self.read_connection.execute(query, parameters or {}) as cursor:
                rows = await cursor.fetchall()

            await EventBus.emit(StorageOnlineEvent())
            return list(rows)
        except Exception:
            await EventBus.emit(StorageOfflineEvent())
            raise

    async def read_meta(self, key: str) -> str | None:
        async with self.read_connection.execute(SELECT_META, (key,)) as cursor:
            row = await cursor.fetchone()

        return None if row is None else str(row[0])

    async def write_meta(self, key: str, value: str) -> None:
        async with self._write_lock:
            await self.write_connection.execute(UPSERT_META, (key, value))

    async def close(self) -> None:
        await EventBus.emit(StorageOfflineEvent())

        if self._read is not None:
            await self._read.close()
            self._read = None

        if self._write is not None:
            await self._write.execute("PRAGMA optimize")
            await self._write.close()
            self._write = None
