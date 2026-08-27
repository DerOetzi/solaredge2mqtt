from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.storage.periods import hour_start
from solaredge2mqtt.core.storage.queries import DELETE_POINTS_BEFORE

if TYPE_CHECKING:
    from solaredge2mqtt.core.storage import StorageService

RAW_MEASUREMENTS = ("powerflow_raw", "battery_raw")

LAST_RETENTION_RUN_KEY = "last_retention_run"

RETENTION_INTERVAL_SECONDS = 86400

VACUUM_PAGES = 2000


async def apply_raw_retention(
    storage: StorageService, now: datetime | None = None
) -> int:
    moment = now or datetime.now(tz=timezone.utc)
    cutoff = int(
        (
            hour_start(moment) - timedelta(hours=storage.settings.retention_raw)
        ).timestamp()
    )

    deleted = 0
    for measurement in RAW_MEASUREMENTS:
        for series_id in await storage.series_ids(measurement):
            deleted += await storage.execute_write(
                DELETE_POINTS_BEFORE, {"series_id": series_id, "cutoff": cutoff}
            )

    if deleted:
        logger.debug(f"Removed {deleted} raw points older than {cutoff}")

    return deleted


async def maybe_apply_long_retention(
    storage: StorageService, now: datetime | None = None
) -> int:
    if storage.settings.retention == 0:
        return 0

    moment = now or datetime.now(tz=timezone.utc)
    timestamp = int(moment.timestamp())

    last_run = await storage.read_meta(LAST_RETENTION_RUN_KEY)
    if last_run is not None and timestamp - int(last_run) < RETENTION_INTERVAL_SECONDS:
        return 0

    cutoff = timestamp - storage.settings.retention

    deleted = 0
    for series_id in await storage.all_series_ids():
        deleted += await storage.execute_write(
            DELETE_POINTS_BEFORE, {"series_id": series_id, "cutoff": cutoff}
        )

    await storage.write_meta(LAST_RETENTION_RUN_KEY, str(timestamp))

    if deleted:
        logger.info(f"Applied retention, removed {deleted} points older than {cutoff}")

    await run_maintenance(storage)

    return deleted


async def run_maintenance(storage: StorageService) -> None:
    await storage.execute_write(f"PRAGMA incremental_vacuum({VACUUM_PAGES})")
    await storage.execute_write("PRAGMA wal_checkpoint(TRUNCATE)")
    await storage.execute_write("PRAGMA optimize")
