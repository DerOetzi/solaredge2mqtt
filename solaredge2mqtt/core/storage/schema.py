from __future__ import annotations

from datetime import datetime, timezone

import aiosqlite

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.logging import logger

SCHEMA_VERSION = 1

CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER NOT NULL,
    applied_at INTEGER NOT NULL
)
"""

CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID
"""

CREATE_SERIES = """
CREATE TABLE IF NOT EXISTS series (
    series_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    measurement TEXT NOT NULL,
    field       TEXT NOT NULL,
    tags        TEXT NOT NULL DEFAULT '',
    UNIQUE (measurement, field, tags)
)
"""

CREATE_SERIES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_series_measurement ON series (measurement, field)
"""

CREATE_SERIES_TAG = """
CREATE TABLE IF NOT EXISTS series_tag (
    series_id INTEGER NOT NULL REFERENCES series(series_id) ON DELETE CASCADE,
    tag_key   TEXT NOT NULL,
    tag_value TEXT NOT NULL,
    PRIMARY KEY (series_id, tag_key)
) WITHOUT ROWID
"""

CREATE_SERIES_TAG_INDEX = """
CREATE INDEX IF NOT EXISTS idx_series_tag_lookup
    ON series_tag (tag_key, tag_value, series_id)
"""

CREATE_POINT = """
CREATE TABLE IF NOT EXISTS point (
    series_id INTEGER NOT NULL REFERENCES series(series_id) ON DELETE CASCADE,
    ts        INTEGER NOT NULL,
    value             ,
    PRIMARY KEY (series_id, ts)
) WITHOUT ROWID
"""

MIGRATIONS: dict[int, tuple[str, ...]] = {
    1: (
        CREATE_SCHEMA_VERSION,
        CREATE_META,
        CREATE_SERIES,
        CREATE_SERIES_INDEX,
        CREATE_SERIES_TAG,
        CREATE_SERIES_TAG_INDEX,
        CREATE_POINT,
    )
}


async def read_schema_version(connection: aiosqlite.Connection) -> int:
    async with connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name = 'schema_version'"
    ) as cursor:
        if await cursor.fetchone() is None:
            return 0

    async with connection.execute("SELECT MAX(version) FROM schema_version") as cursor:
        row = await cursor.fetchone()

    if row is None or row[0] is None:
        return 0

    return int(row[0])


async def migrate(connection: aiosqlite.Connection) -> int:
    current = await read_schema_version(connection)

    if current > SCHEMA_VERSION:
        raise ConfigurationException(
            "storage",
            f"Database schema version {current} is newer than the supported "
            f"version {SCHEMA_VERSION}. Downgrading is not supported.",
        )

    for version in range(current + 1, SCHEMA_VERSION + 1):
        logger.info(f"Applying storage schema migration {version}")
        for statement in MIGRATIONS[version]:
            await connection.execute(statement)

        await connection.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, int(datetime.now(tz=timezone.utc).timestamp())),
        )
        await connection.commit()

    return SCHEMA_VERSION
