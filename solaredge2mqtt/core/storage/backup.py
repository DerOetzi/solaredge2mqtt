from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from shutil import disk_usage
from sqlite3 import Error as SQLiteError
from typing import TYPE_CHECKING

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.storage.connection import DATABASE_FILE_MODE

if TYPE_CHECKING:
    from solaredge2mqtt.core.storage import StorageService

LAST_BACKUP_KEY = "last_backup"

BACKUP_INTERVAL_SECONDS = 86400

BACKUP_INFIX = ".backup."

TIMESTAMP_FORMAT = "%Y%m%d%H%M%S"


def backup_path(db_path: Path, moment: datetime) -> Path:
    """Name a backup after the database and the moment it was taken."""
    return db_path.with_name(
        f"{db_path.name}{BACKUP_INFIX}{moment.strftime(TIMESTAMP_FORMAT)}"
    )


def existing_backups(db_path: Path) -> list[Path]:
    """List the backups of one database, the newest first.

    The timestamp format sorts lexicographically, so the file names order
    themselves without touching the filesystem metadata.
    """
    pattern = f"{db_path.name}{BACKUP_INFIX}*"
    return sorted(db_path.parent.glob(pattern), reverse=True)


def prune_backups(db_path: Path, keep: int) -> list[Path]:
    """Delete all but the newest `keep` backups, `keep` of 0 keeps every one."""
    if keep == 0:
        return []

    obsolete = existing_backups(db_path)[keep:]

    for path in obsolete:
        path.unlink(missing_ok=True)
        logger.info(f"Removed obsolete database backup '{path}'")

    return obsolete


def has_room_for_backup(db_path: Path) -> bool:
    """Check that the filesystem can hold a second copy of the database."""
    return disk_usage(db_path.parent).free > db_path.stat().st_size


async def create_backup(storage: StorageService, moment: datetime) -> Path | None:
    """Copy the database through SQLite, returning the backup that was written.

    A failure is logged and swallowed rather than reported as a storage
    outage: the service keeps reading and writing its history either way, and
    a full filesystem must not take the whole storage offline.
    """
    target = backup_path(storage.db_path, moment)

    if target.exists():
        logger.warning(f"Database backup '{target}' already exists, skipping")
        return None

    if not has_room_for_backup(storage.db_path):
        logger.warning(
            f"Not enough free disk space for a backup of '{storage.db_path}', skipping"
        )
        return None

    try:
        await storage.vacuum_into(target)
    except (SQLiteError, OSError) as error:
        logger.error(f"Failed to write database backup '{target}': {error}")
        target.unlink(missing_ok=True)
        return None

    target.chmod(DATABASE_FILE_MODE)
    logger.info(f"Wrote database backup '{target}'")

    return target


async def maybe_create_backup(
    storage: StorageService, now: datetime | None = None
) -> Path | None:
    """Write a backup once a day and drop the ones beyond `keep_backups`."""
    if not storage.settings.daily_backups:
        return None

    moment = now or datetime.now(tz=timezone.utc)
    timestamp = int(moment.timestamp())

    last_run = await storage.read_meta(LAST_BACKUP_KEY)
    if last_run is not None and timestamp - int(last_run) < BACKUP_INTERVAL_SECONDS:
        return None

    backup = await create_backup(storage, moment)
    if backup is None:
        return None

    await storage.write_meta(LAST_BACKUP_KEY, str(timestamp))
    prune_backups(storage.db_path, storage.settings.keep_backups)

    return backup
