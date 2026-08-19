from __future__ import annotations

from pathlib import Path

import aiosqlite

from solaredge2mqtt.core.logging import logger

WRITE_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA cache_size=-16000",
)

READ_PRAGMAS = (
    "PRAGMA busy_timeout=5000",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA cache_size=-16000",
    "PRAGMA query_only=ON",
)

DATABASE_FILE_MODE = 0o600


async def open_write_connection(db_path: Path) -> aiosqlite.Connection:
    is_new = not db_path.exists()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = await aiosqlite.connect(db_path, isolation_level=None)
    connection.row_factory = aiosqlite.Row

    if is_new:
        await connection.execute("PRAGMA auto_vacuum=INCREMENTAL")

    for pragma in WRITE_PRAGMAS:
        await connection.execute(pragma)

    if is_new:
        db_path.chmod(DATABASE_FILE_MODE)

    if not await supports_incremental_vacuum(connection):
        logger.info(
            "Database was created without incremental auto vacuum, "
            "free pages are not returned to the filesystem automatically."
        )

    return connection


async def open_read_connection(db_path: Path) -> aiosqlite.Connection:
    connection = await aiosqlite.connect(
        f"file:{db_path}?mode=ro", uri=True, isolation_level=None
    )
    connection.row_factory = aiosqlite.Row

    for pragma in READ_PRAGMAS:
        await connection.execute(pragma)

    return connection


async def supports_incremental_vacuum(connection: aiosqlite.Connection) -> bool:
    async with connection.execute("PRAGMA auto_vacuum") as cursor:
        row = await cursor.fetchone()

    return row is not None and int(row[0]) == 2
